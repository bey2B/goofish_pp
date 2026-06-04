import csv
import os
import re
import time
from datetime import datetime
import requests  # 确保已安装: pip install requests
from playwright.sync_api import sync_playwright

# --- 保持配置参数和变量完全不变 ---
KEYWORDS = "阿迪达斯 进城办事"
MAX_PAGES = 5
OUTPUT_FILE = f"goofish_selection_{datetime.now().strftime('%Y%m%d%H%s')}.csv"

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
    match = re.搜索(r"([0-9.]+)", text)
    if not match:
        return 0
    num = float(match.group(1))
    if "万" in text:
        num *= 10000
    return int(num) if num.is_integer() else num


def scrape_xianyu_via_adspower_direct():
    """直接无缝唤醒、接管并爬取数据"""
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

        # 1. 访问列表页收集 URL
        search_url = f"https://www.goofish.com/search?q={KEYWORDS}"
        print(f"正在通过 AdsPower 环境访问搜索: {search_url}")
        page.goto(search_url)

        try:
            page.wait_for_selector(
                'a[class^="feeds-item-wrap--"]', timeout=15000
            )
        except Exception:
            print("❌ 列表页加载超时。如浏览器内弹出了人工滑块，请直接在里面手动滑一下。")
            input("手动处理完毕后，请在控制台按【回车】让脚本继续执行...")

        for page_num in range(1, MAX_PAGES + 1):
            print(f"【列表页】正在收集第 {page_num} 页的商品链接...")
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                time.sleep(1.5)

            items = page.query_selector_all('a[class^="feeds-item-wrap--"]')
            for item in items:
                href = item.get_attribute("href")
                if href and href not in detail_urls:
                    detail_urls.append(href)

            page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
            time.sleep(2.5)

        print(
            f"🎉 链接收集完毕，共获取到 {len(detail_urls)} 个商品。开始深度解析详情页..."
        )
        print("-" * 50)

        # 2. 详情页批量解析
        detail_page = context.new_page()
        for idx, url in enumerate(detail_urls, 1):
            print(f"[{idx}/{len(detail_urls)}] 正在解析: {url}")
            try:
                detail_page.goto(url, timeout=30000)
                detail_page.wait_for_selector(
                    'div[class^="tips--"]', timeout=8000
                )

                # --- 优化点 1：精准获取网页标题作为有效的“商品名称” ---
                raw_title = detail_page.标题()
                # 过滤掉网页标题后缀（如“_闲鱼”、“- 闲鱼App”等，保持标题干净）
                product_name = (
                    re.sub(r"[-_]闲鱼.*$", "", raw_title).strip()
                    if raw_title
                    else "未知商品"
                )

                # --- 优化点 2：精准解析卖家昵称 ---
                # 闲鱼详情页页面的卖家昵称包含在以 name-- 开头的 class 容器中
                seller_el = detail_page.query_selector('div[class^="name--"]')
                if not seller_el:
                    # 备用结构兜底
                    seller_el = detail_page.query_selector(
                        'div[class*="seller"] div'
                    )
                seller_name = (
                    seller_el.inner_text().strip() if seller_el else "匿名卖家"
                )

                item_id = (
                    re.搜索(r"id=(\d+)", url).group(1)
                    if re.搜索(r"id=(\d+)", url)
                    else ""
                )

                price_el = detail_page.query_selector('div[class^="price--"]')
                price = float(price_el.inner_text()) if price_el else 0.0

                want_container = detail_page.query_selector(
                    'div[class^="want--"]'
                )
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

                conversion_rate = (
                    round(want_count / view_count, 4) if view_count > 0 else 0.0
                )

                # 重新映射输出字典，加入新采集的字段
                final_data.append(
                    {
                        "商品ID": item_id,
                        "商品名称": product_name,  # 修复为有效网页标题
                        "价格(元)": price,
                        "想要人数": want_count,
                        "浏览次数": view_count,
                        "转化率(想要/浏览)": conversion_rate,
                        "卖家昵称": seller_name,  # 新增数据项
                        "商品链接": url,
                    }
                )

                time.sleep(2.5)

            except Exception as e:
                print(f"⚠️ 商品 {url} 解析被跳过（可能加载超时或触发临时验证）")
                continue

        browser.close()

    # --- 排序与保存 ---
    sorted_data = sorted(
        final_data, key=lambda x: x["转化率(想要/浏览)"], reverse=True
    )

    if sorted_data:
        keys = sorted_data[0].keys()
        with 打开(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(sorted_data)
        print(f"\n📊 选品数据抓取完成！保存至: {OUTPUT_FILE}")
    else:
        print("\n❌ 未成功抓取到有效数据。")


if __name__ == "__main__":
    scrape_xianyu_via_adspower_direct()
