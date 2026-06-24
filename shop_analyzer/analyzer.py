"""核心分析逻辑 - 读取 CSV、构建提示词、调用 LLM、生成报告"""

import csv
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from openai import OpenAI

from .models import ShopItem
from .prompts import ANALYSIS_SYSTEM_PROMPT, ANALYSIS_USER_PROMPT_TEMPLATE


# ── CSV 读写 ──────────────────────────────────────────────────────

def read_csv(path: str | Path) -> List[ShopItem]:
    """读取闲鱼店铺 CSV 文件，返回 ShopItem 列表"""
    items: List[ShopItem] = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(ShopItem.from_csv_row(row))
    return items


def format_csv_text(items: List[ShopItem]) -> str:
    """将 ShopItem 列表格式化为 CSV 文本（含表头），用于填入提示词"""
    if not items:
        return "(无数据)"
    header = ",".join(ShopItem.field_names())
    lines = [header]
    for item in items:
        row = item.to_csv_dict()
        lines.append(
            ",".join(
                str(row.get(field, "")).replace(",", "，")
                for field in ShopItem.field_names()
            )
        )
    return "\n".join(lines)


# ── 聚合统计 ──────────────────────────────────────────────────────

def compute_summary(items: List[ShopItem]) -> dict:
    """计算商品数据的聚合统计"""
    total = len(items)
    if total == 0:
        return {"total": 0, "avg_price": 0, "avg_conversion": 0, "total_wants": 0}

    prices = [it.价格_元 for it in items]
    want_counts = sorted([it.想要人数 for it in items], reverse=True)
    total_wants = sum(want_counts)

    # 头部集中度：Top 5% 商品贡献的想要数占比
    top_n = max(1, total // 20)
    top_wants = sum(want_counts[:top_n])
    concentration = round(top_wants / total_wants, 4) if total_wants > 0 else 0

    # 转化率统计
    conversions = [it.转化率_想要_浏览 for it in items if it.浏览次数 > 0]
    avg_conversion = round(sum(conversions) / len(conversions), 4) if conversions else 0

    # 卖家去重
    sellers = set(it.卖家昵称 for it in items)

    return {
        "total": total,
        "avg_price": round(sum(prices) / total, 2),
        "max_price": max(prices),
        "min_price": min(prices),
        "total_wants": total_wants,
        "top_concentration": concentration,
        "avg_conversion": avg_conversion,
        "unique_sellers": len(sellers),
        "active_items": sum(1 for it in items if it.卖家昵称 != "下架"),
        "sold_out_items": sum(1 for it in items if it.卖家昵称 == "下架"),
    }


# ── 提示词构建 ────────────────────────────────────────────────────

def build_prompt(items: List[ShopItem]) -> str:
    """构建发送给 LLM 的完整提示词"""
    csv_text = format_csv_text(items)
    summary = compute_summary(items)

    # 在 CSV 数据前加上聚合摘要，让 AI 看到更多上下文
    summary_block = (
        f"【数据概览】\n"
        f"商品总数: {summary['total']}\n"
        f"活跃商品: {summary['active_items']} | 已下架: {summary['sold_out_items']}\n"
        f"平均价格: ¥{summary['avg_price']} | 价格区间: ¥{summary['min_price']} ~ ¥{summary['max_price']}\n"
        f"总想要数: {summary['total_wants']}\n"
        f"头部集中度(Top5%): {summary['top_concentration']*100:.1f}%\n"
        f"平均转化率: {summary['avg_conversion']*100:.2f}%\n"
        f"卖家数量: {summary['unique_sellers']}\n\n"
    )

    return ANALYSIS_USER_PROMPT_TEMPLATE.format(
        csv_data=summary_block + csv_text
    )


# ── AI 调用 ────────────────────────────────────────────────────────

def analyze_shop(items: List[ShopItem], client: OpenAI, model: str, temperature: float = 0.3) -> str:
    """发送商品数据到 LLM 进行分析，返回分析报告 Markdown"""
    prompt = build_prompt(items)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=8192,
    )
    return response.choices[0].message.content


# ── 报告保存 ──────────────────────────────────────────────────────

def save_report(report: str, csv_path: str | Path) -> str:
    """将分析报告保存为 Markdown 文件，返回文件路径"""
    csv_path = Path(csv_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = csv_path.stem  # 不含扩展名的文件名

    report_filename = f"{stem}_analysis_{timestamp}.md"
    report_path = csv_path.parent / report_filename

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    return str(report_path)


# ── 高层接口 ──────────────────────────────────────────────────────

def analyze_from_csv(csv_path: str | Path, client: OpenAI, model: str) -> Tuple[str, str]:
    """从 CSV 文件进行全流程分析，返回 (报告内容, 报告保存路径)"""
    csv_path = Path(csv_path)
    items = read_csv(csv_path)

    if not items:
        raise ValueError(f"CSV 文件 '{csv_path}' 中没有有效数据")

    report = analyze_shop(items, client, model)
    report_path = save_report(report, csv_path)
    return report, report_path


def print_report_summary(report: str, report_path: str) -> None:
    """在终端打印报告摘要"""
    # 提取前几个段落作为摘要
    lines = report.strip().split("\n")
    summary_lines = []
    section_count = 0
    for line in lines:
        summary_lines.append(line)
        if line.startswith("### ") or line.startswith("## "):
            section_count += 1
        if section_count >= 2 and line.strip() == "":
            break

    print("\n" + "=" * 60)
    print(f"  店铺分析报告已生成")
    print("=" * 60)
    print("\n".join(summary_lines))
    print(f"\n... (完整报告已保存至: {report_path})")
    print("=" * 60)
