#!/usr/bin/env python3
"""闲鱼店铺 CSV 数据 AI 分析的快捷入口脚本

用法:
    python analyze_shop.py --csv xianyu_shop_deep_20260614_160802.csv
    python analyze_shop.py --all
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from shop_analyzer.cli import main

if __name__ == "__main__":
    main()
