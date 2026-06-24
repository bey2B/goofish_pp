import csv
import os
import re
import time
from datetime import datetime
import requests
from playwright.sync_api import sync_playwright
# 是否自动运行 AI 分析
AUTO_ANALYZE = False

from shop_analyzer.analyzer import analyze_from_csv, print_report_summary
from shop_analyzer.config import build_client, check_config, get_model
import argparse
import sys

# --- AdsPower 接口配置 ---
ADS_API_PORT = 50325  # 你的 AdsPower 端口

# --- 指定你要启动的环境 (保持不变) ---
ENV_SERIAL_NUMBER = "1"  # 序号
ENV_USER_ID = None  # 账号ID


def start_and_get_adspower_ws():
    """通过 serial_number 或 user_id 唤醒 AdsPower 并获取调试端口"""
    params = {}
    if ENV_USER_ID:
        params["user_id"] = ENV_USER_ID
    elif ENV_SERIAL_NUMBER:
        params["serial_number"] = ENV_SERIAL_NUMBER
    else:
        print("❌ 请在代码上方配置 ENV_SERIAL_NUMBER 或 ENV_USER_ID")
        return None

    try:
        url = f"http://127.0.0.1:{ADS_API_PORT}/api/v1/browser/start"
        print(f"🚀 正在请求 AdsPower 启动/接管环境 [序号: {ENV_SERIAL_NUMBER}]...")
        response = requests.get(url, params=params).json()

        if response.get("code") == 0 and response.get("data"):
            return response["data"]["ws"]["puppeteer"]
        else:
            print(f"❌ AdsPower 启动失败: {response.get('msg')}")
            return None
    except Exception as e:
        print(f"❌ 无法连接到 AdsPower 本地 API。错误: {e}")
    return None


def parse_numeric(text):
    """提取文本中的数字"""
    if not text:
        return 0
    text = text.strip()
    match = re.search(r"([0-9.]+)", text)
    if not match:
        return 0
    num = float(match.group(1))
    if "万" in text:
        num *= 10000
    return int(num) if num.is_integer() else num


def scrape_xianyu_shop_deep():
    # 1. 动态输入店铺链接
    shop_url = input("🔗 请输入你要扒取的闲鱼店铺链接: ").strip()
    if not shop_url:
        print("❌ 店铺链接不能为空！")
        return

    output_file = f"xianyu_shop_deep_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    # 2. 连接 AdsPower
    ws_url = start_and_get_adspower_ws()
    if not ws_url:
        return

    detail_urls = []
    final_data = []

    with sync_playwright() as p:
        print(f"🌐 Playwright 已成功连接到 AdsPower 指纹环境...")
        browser = p.chromium.connect_over_cdp(ws_url)
        context = browser.contexts[0]
        page = context.new_page()

        # ---------------- 阶段一：访问店铺主页滚动收集所有商品 URL ----------------
        print(f"正在打开店铺页面: {shop_url}")
        page.goto(shop_url)

        try:
            page.wait_for_selector('a[class^="feeds-item-wrap--"]', timeout=15000)
        except Exception:
            print("❌ 店铺商品加载超时。如浏览器内弹出了验证码，请手动滑一下。")
            input("手动处理完毕后，请在控制台按【回车】让脚本继续执行...")

        print("⏳ 开始在店铺页向下滚动收集商品链接（自动去重触底）...")
        no_new_items_count = 0

        while True:
            current_url_count = len(detail_urls)

            # 向下滚动
            page.evaluate("window.scrollBy(0, window.innerHeight * 1.5)")
            time.sleep(1.5)

            # 根据你提供的最新 DOM，精准匹配商品卡片 a 标签
            items = page.query_selector_all('a[class^="feeds-item-wrap--"]')
            for item in items:
                href = item.get_attribute("href")
                if href:
                    if href.startswith("//"):
                        href = "https:" + href
                    if href not in detail_urls:
                        detail_urls.append(href)

            print(f" 🔁 当前已收集商品链接: {len(detail_urls)} 个...")

            # 触底检测：如果连续 5 次滚动链接数量不再增加，判定全店商品已加载完
            if len(detail_urls) == current_url_count:
                no_new_items_count += 1
                if no_new_items_count >= 5:
                    print("🏁 已检测到店铺底部，商品链接收集完毕！")
                    break
            else:
                no_new_items_count = 0

        print(f"\n🎉 链接收集完毕，店铺共获取到 {len(detail_urls)} 个商品。")
        print("-" * 60)
        print("🚀 启动详情页批量二次跳转解析（深度抓取 想要/浏览量/转化率）...")
        print("-" * 60)

        # ---------------- 阶段二：详情页批量二次跳转解析 ----------------
        detail_page = context.new_page()
        for idx, url in enumerate(detail_urls, 1):
            print(f"[{idx}/{len(detail_urls)}] 正在深度解析: {url}")
            try:
                detail_page.goto(url, timeout=30000)
                # 等待商品详情页面底部包含 想要/浏览 的提示容器加载
                detail_page.wait_for_selector('div[class^="tips--"]', timeout=8000)

                # 1. 精准获取网页标题作为商品名称
                raw_title = detail_page.title()
                product_name = (
                    re.sub(r"[-_]闲鱼.*$", "", raw_title).strip()
                    if raw_title
                    else "未知商品"
                )

                # 2. 精准解析卖家昵称
                seller_el = detail_page.query_selector('div[class^="name--"]')
                if not seller_el:
                    seller_el = detail_page.query_selector('div[class*="seller"] div')
                seller_name = seller_el.inner_text().strip() if seller_el else "匿名卖家"

                # 3. 提取商品 ID
                item_id = ""
                id_match = re.search(r"id=(\d+)", url)
                if id_match:
                    item_id = id_match.group(1)

                # 4. 解析价格
                price_el = detail_page.query_selector('div[class^="price--"]')
                price = float(price_el.inner_text()) if price_el else 0.0

                # 5. 二级跳转的核心：获取详情页底部的精确 [想要数] 与 [浏览数]
                want_container = detail_page.query_selector('div[class^="want--"]')
                want_count = 0
                view_count = 0

                if want_container:
                    divs = want_container.query_selector_all("div")
                    for d in divs:
                        text = d.inner_text()
                        if "想要" in text:
                            want_count = parse_numeric(text)
                        elif "浏览" in text:
                            view_count = parse_numeric(text)

                # 6. 计算更精准的截流指标：转化率
                conversion_rate = (
                    round(want_count / view_count, 4) if view_count > 0 else 0.0
                )

                # 存入结果列表
                final_data.append(
                    {
                        "商品ID": item_id,
                        "商品名称": product_name,
                        "价格(元)": price,
                        "想要人数": want_count,
                        "浏览次数": view_count,
                        "转化率(想要/浏览)": conversion_rate,
                        "卖家昵称": seller_name,
                        "商品链接": url,
                    }
                )

                # 详情页之间设置合理的爬取间隔，降低风控风险
                time.sleep(2.5)

            except Exception as e:
                print(f"⚠️ 商品 {url} 解析被跳过（可能加载超时或触发临时滑块）")
                continue

        browser.close()

    # --- 核心排序：按【想要人数】降序排列，找出店铺真正的销售爆款 ---
    sorted_data = sorted(
        final_data, key=lambda x: x["想要人数"], reverse=True
    )

    # --- 写入 CSV 保存结果 ---
    if sorted_data:
        keys = sorted_data[0].keys()
        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(sorted_data)

        print(f"\n📊 【爆款分析完成】店铺选品数据已保存至: {output_file}")
        print("💡 推荐截流策略：优先看表格最上方的数据（按想要人数从高到低排列），这些是该店出单最稳的顶流产品！")
    else:
        print("\n❌ 未成功抓取到任何有效的详情页数据。")


def _maybe_analyze(csv_path: str) -> None:
    """分析完成后，询问是否进行 AI 分析"""
    if not check_config():
        return
    if not AUTO_ANALYZE:
        answer = input('\n是否对数据进行 AI 深度分析？(y/N): ').strip().lower()
        if answer not in ('y', 'yes'):
            print('已跳过 AI 分析。')
            return
    else:
        print('\n正在自动进行 AI 深度分析...')
    client = build_client()
    if not client:
        return
    model = get_model()
    if not model:
        return
    try:
        report, report_path = analyze_from_csv(csv_path, client, model)
        print_report_summary(report, report_path)
    except Exception as e:
        print(f'\nAI 分析出错: {e}')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='闲鱼店铺深度爬虫')
    parser.add_argument('--auto-analyze', action='store_true', help='爬取后自动运行 AI 分析')
    args = parser.parse_args()
    AUTO_ANALYZE = args.auto_analyze
    scrape_xianyu_shop_deep()
