"""命令行入口 - 分析闲鱼店铺 CSV 数据"""

import argparse
import sys
from pathlib import Path

from .analyzer import analyze_from_csv, print_report_summary, read_csv, compute_summary
from .config import build_client, check_config, get_model


def find_shop_csvs(root: str | Path = ".") -> list[Path]:
    """查找所有闲鱼店铺 CSV 文件"""
    root = Path(root)
    return sorted(root.glob("xianyu_shop_deep_*.csv"))


def analyze_one(csv_path: str | Path) -> bool:
    """分析单个 CSV 文件，返回是否成功"""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"文件不存在: {csv_path}")
        return False

    # 先加载数据做个快速预览
    items = read_csv(csv_path)
    summary = compute_summary(items)
    print(f"\n文件: {csv_path.name}")
    print(f"  商品数: {summary['total']} | 活跃: {summary['active_items']} | 下架: {summary['sold_out_items']}")
    print(f"  均价: {summary['avg_price']}元 | 总想要数: {summary['total_wants']}")
    sys.stdout.flush()

    print(f"\n正在调用 AI 进行分析...")
    sys.stdout.flush()
    report, report_path = analyze_from_csv(csv_path, build_client(), get_model())
    print_report_summary(report, report_path)
    return True


def main():
    if not check_config():
        sys.exit(1)

    client = build_client()
    if not client:
        sys.exit(1)

    model = get_model()
    if not model:
        sys.exit(1)

    parser = argparse.ArgumentParser(description="闲鱼店铺数据 AI 分析工具")
    parser.add_argument(
        "--csv", type=str, default=None,
        help="要分析的 CSV 文件路径"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="分析当前目录下所有 xianyu_shop_deep_*.csv 文件"
    )
    args = parser.parse_args()

    if args.csv:
        ok = analyze_one(args.csv)
        sys.exit(0 if ok else 1)

    elif args.all:
        csv_files = find_shop_csvs()
        if not csv_files:
            print("当前目录下没有找到 xianyu_shop_deep_*.csv 文件")
            sys.exit(1)
        print(f"找到 {len(csv_files)} 个 CSV 文件，开始分析...")
        success_count = 0
        for f in csv_files:
            if analyze_one(f):
                success_count += 1
        print(f"\n分析完成: {success_count}/{len(csv_files)} 成功")
        sys.exit(0 if success_count == len(csv_files) else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
