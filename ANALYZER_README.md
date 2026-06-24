# 闲鱼店铺数据 AI 分析系统

在现有闲鱼店铺爬虫 (`dianpu.py`) 的基础上，构建了完整的 AI 分析管道：

抓取店铺商品数据 → CSV 持久化 → 读取 CSV → 调用 LLM（OpenAI 兼容接口）→ 生成专业店铺诊断报告（Markdown）


## 快速开始

### 1. 配置 AI

在项目根目录创建 `.env` 文件（已提供模板），配置 AI 模型信息：

```env
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api-inference.modelscope.cn/v1/
OPENAI_MODEL_NAME=XiaomiMiMo/MiMo-V2-Flash
```

> 支持任何 OpenAI 兼容 API（如 OpenAI、ModelScope、DeepSeek、通义千问等）。

### 2. 安装依赖

```bash
pip install openai python-dotenv
```

### 3. 运行分析

#### 方式一：爬取后自动分析

```bash
python dianpu.py
```

爬取完成后会询问是否进行 AI 分析：

```
是否对数据进行 AI 深度分析？(y/N): y
```

如需完全自动化（跳过询问）：

```bash
python dianpu.py --auto-analyze
```

#### 方式二：分析已有 CSV 文件

分析单个文件：

```bash
python analyze_shop.py --csv xianyu_shop_deep_20260614_160802.csv
```

批量分析所有店铺 CSV：

```bash
python analyze_shop.py --all
```

#### 方式三：作为 Python 模块调用

```python
from shop_analyzer.analyzer import analyze_from_csv
from shop_analyzer.config import build_client, get_model

client = build_client()
model = get_model()
report, report_path = analyze_from_csv("xianyu_shop_deep_20260614_160802.csv", client, model)
print(report)  # Markdown 格式的报告
```


## 输出说明

分析完成后，在 CSV 同级目录生成 Markdown 报告文件：

```
xianyu_shop_deep_20260614_160802.csv
xianyu_shop_deep_20260614_160802_analysis_20260624_164500.md
```

报告按以下结构输出：

| 章节 | 内容 |
|------|------|
| 整体店铺诊断 | 商品数、活跃/下架比例、流量集中度、平均价格、转化率 |
| 商品表现分层分析 | Top 爆款、潜力品、僵尸品、实物 vs 虚拟对比 |
| 选品与定价策略建议 | 选品方向、品类推荐、客单价提升方案 |
| 标题与运营优化 | Top 3 商品标题优化、主图/详情建议 |
| 整体陪跑策略 | 短期/中期动作、风险提醒 |


## 项目结构

```
Goofish/
├── .env                         # AI 配置（从 ai-goofish-monitor 复用）
├── dianpu.py                    # 店铺爬虫（已集成 AI 分析）
├── analyze_shop.py              # CSV 分析快捷入口
├── shop_analyzer/
│   ├── __init__.py              # 包标记
│   ├── models.py                # ShopItem 数据模型
│   ├── config.py                # 配置加载（OpenAI 客户端）
│   ├── prompts.py               # AI 分析提示词模板
│   ├── analyzer.py              # 核心分析逻辑
│   └── cli.py                   # 命令行入口
├── tests/
│   ├── __init__.py
│   ├── test_analyzer.py         # 分析器单元测试
│   ├── test_config.py           # 配置管理测试
│   └── fixtures/
│       └── sample_shop.csv      # 测试样本数据
└── ANALYZER_README.md           # 本文件
```


## 测试

```bash
python -m pytest tests/ -v
```

覆盖内容：

- 数据模型构建与分层判定（爆款/潜力/僵尸）
- CSV 解析（含字段缺失、空文件等边界）
- 聚合统计计算
- 提示词模板渲染
- 报告保存
- 配置管理与环境变量缺失处理


## 设计要点

- **复用现有配置**：`.env` 字段与 `ai-goofish-monitor` 兼容，共享 `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL_NAME`
- **免额外依赖**：仅需 `openai` + `python-dotenv`（均已安装）
- **独立可测试**：`shop_analyzer/` 模块无外部依赖（除 OpenAI），所有逻辑可单元测试
- **CSV 格式兼容**：直接读取 `dianpu.py` 输出的 utf-8-sig 编码 CSV 文件
- **报告可读**：AI 分析结果保存为 Markdown 格式，可直接在 VS Code / Typora / GitHub 中查看
