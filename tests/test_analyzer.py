"""测试 - 分析器核心逻辑"""

import csv
import os
import tempfile
from pathlib import Path

import pytest

from shop_analyzer.models import ShopItem
from shop_analyzer.analyzer import (
    read_csv,
    format_csv_text,
    compute_summary,
    build_prompt,
    save_report,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sample_shop.csv"


# ── 模型测试 ──────────────────────────────────────────────────────

def test_shop_item_from_csv_row():
    row = {
        "商品ID": "972741150394",
        "商品名称": "测试商品",
        "价格(元)": "1.5",
        "想要人数": "100",
        "浏览次数": "500",
        "转化率(想要/浏览)": "0.2",
        "卖家昵称": "测试卖家",
        "商品链接": "https://goofish.com/item?id=972741150394",
    }
    item = ShopItem.from_csv_row(row)
    assert item.商品ID == "972741150394"
    assert item.商品名称 == "测试商品"
    assert item.价格_元 == 1.5
    assert item.想要人数 == 100
    assert item.浏览次数 == 500
    assert item.转化率_想要_浏览 == 0.2
    assert item.卖家昵称 == "测试卖家"


def test_shop_item_zombie_detection():
    """僵尸品判定：想要数 <= 2 且 浏览 < 200"""
    zombie = ShopItem(想要人数=1, 浏览次数=50)
    assert zombie.is_zombie is True

    not_zombie = ShopItem(想要人数=3, 浏览次数=50)
    assert not_zombie.is_zombie is False

    high_view = ShopItem(想要人数=1, 浏览次数=300)
    assert high_view.is_zombie is False


def test_shop_item_potential_detection():
    """潜力品判定"""
    # 想要数在 5-10 之间
    p1 = ShopItem(想要人数=7, 浏览次数=1000)
    assert p1.is_potential is True

    # 转化率高但曝光低
    p2 = ShopItem(想要人数=3, 浏览次数=100, 转化率_想要_浏览=0.15)
    assert p2.is_potential is True

    # 普通商品
    normal = ShopItem(想要人数=3, 浏览次数=1000, 转化率_想要_浏览=0.03)
    assert normal.is_potential is False


def test_shop_item_hot_detection():
    hot = ShopItem(想要人数=200)
    assert hot.is_hot is True

    not_hot = ShopItem(想要人数=199)
    assert not_hot.is_hot is False


def test_shop_item_to_csv_dict():
    item = ShopItem(
        商品ID="123", 商品名称="测试", 价格_元=9.9, 想要人数=50,
        浏览次数=500, 转化率_想要_浏览=0.1, 卖家昵称="卖家", 商品链接="https://example.com",
    )
    d = item.to_csv_dict()
    assert d["商品ID"] == "123"
    assert d["价格(元)"] == 9.9


# ── CSV 解析测试 ──────────────────────────────────────────────────

def test_read_csv():
    items = read_csv(FIXTURE_PATH)
    assert len(items) == 8
    assert items[0].商品名称 == "《暗黑破坏神2重制版-终极包》中文豪华版PC电脑单机游戏全DLC"
    assert items[0].价格_元 == 0.85


def test_read_csv_empty(tmp_path):
    """空 CSV 应返回空列表"""
    empty_csv = tmp_path / "empty.csv"
    with open(empty_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ShopItem.field_names())
        writer.writeheader()
    items = read_csv(empty_csv)
    assert items == []


def test_read_csv_partial_fields(tmp_path):
    """缺失字段应使用默认值"""
    partial_csv = tmp_path / "partial.csv"
    with open(partial_csv, "w", encoding="utf-8-sig", newline="") as f:
        f.write("商品ID,商品名称\n")
        f.write("123,部分数据\n")
    items = read_csv(partial_csv)
    assert len(items) == 1
    assert items[0].商品ID == "123"
    assert items[0].价格_元 == 0.0


def test_format_csv_text():
    items = read_csv(FIXTURE_PATH)
    text = format_csv_text(items)
    assert "商品ID" in text
    assert "暗黑破坏神" in text
    assert text.count("\n") == 8  # 9 lines (1 header + 8 data) → 8 newlines


def test_format_csv_text_empty():
    assert format_csv_text([]) == "(无数据)"


# ── 聚合统计测试 ──────────────────────────────────────────────────

def test_compute_summary():
    items = read_csv(FIXTURE_PATH)
    s = compute_summary(items)
    assert s["total"] == 8
    assert s["avg_price"] == pytest.approx(0.975, 0.01)
    assert s["max_price"] == 1.6
    assert s["min_price"] == 0.8
    assert s["total_wants"] > 0
    assert s["active_items"] >= 6
    assert s["sold_out_items"] >= 1  # 下架卖家


def test_compute_summary_empty():
    assert compute_summary([])["total"] == 0


def test_compute_summary_single_item():
    item = ShopItem(商品名称="唯一商品", 价格_元=99, 想要人数=10, 浏览次数=100, 转化率_想要_浏览=0.1, 卖家昵称="卖家")
    s = compute_summary([item])
    assert s["total"] == 1
    assert s["avg_price"] == 99.0
    assert s["avg_conversion"] == 0.1
    assert s["top_concentration"] == 1.0


# ── 提示词构建测试 ──────────────────────────────────────────────

def test_build_prompt():
    items = read_csv(FIXTURE_PATH)
    prompt = build_prompt(items)
    assert "【数据概览】" in prompt
    assert "商品总数" in prompt
    assert "CSV格式" in prompt
    assert "整体店铺诊断" in prompt
    assert "Top爆款" in prompt
    assert "暗黑破坏神" in prompt


# ── 报告保存测试 ──────────────────────────────────────────────────

def test_save_report(tmp_path):
    report_text = "## 分析报告\n\n测试内容"
    csv_path = tmp_path / "xianyu_shop_deep_20260614_test.csv"
    csv_path.write_text("", encoding="utf-8")

    saved = save_report(report_text, csv_path)
    assert Path(saved).exists()
    assert Path(saved).read_text(encoding="utf-8") == report_text
    assert "_analysis_" in saved
    assert saved.endswith(".md")
