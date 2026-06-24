"""配置管理 - 从 .env 加载 AI 配置"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

# 从项目根目录加载 .env
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

# --- AI 配置 ---
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL")
MODEL_NAME = os.getenv("OPENAI_MODEL_NAME")
PROXY_URL = os.getenv("PROXY_URL", "")

# --- 验证 ---
_config_ok = all([BASE_URL, MODEL_NAME])


def check_config() -> bool:
    """检查 AI 配置是否完整，不完整时打印警告"""
    if not _config_ok:
        print(
            "╔══════════════════════════════════════════════════════╗\n"
            "║  AI 分析功能不可用                                  ║\n"
            "║  请在项目根目录创建 .env 文件，并配置：              ║\n"
            "║    OPENAI_BASE_URL=https://api.openai.com/v1/       ║\n"
            "║    OPENAI_MODEL_NAME=gpt-4o                         ║\n"
            "║    OPENAI_API_KEY=sk-... (某些服务可选)              ║\n"
            "╚══════════════════════════════════════════════════════╝"
        )
        return False
    return True


def build_client() -> OpenAI | None:
    """构建同步 OpenAI 客户端"""
    if not _config_ok:
        return None
    try:
        client_kwargs = {"api_key": API_KEY, "base_url": BASE_URL}
        if PROXY_URL:
            os.environ["HTTP_PROXY"] = PROXY_URL
            os.environ["HTTPS_PROXY"] = PROXY_URL
        return OpenAI(**client_kwargs)
    except Exception as e:
        print(f"初始化 OpenAI 客户端失败: {e}")
        return None


def build_async_client() -> AsyncOpenAI | None:
    """构建异步 OpenAI 客户端"""
    if not _config_ok:
        return None
    try:
        client_kwargs = {"api_key": API_KEY, "base_url": BASE_URL}
        if PROXY_URL:
            os.environ["HTTP_PROXY"] = PROXY_URL
            os.environ["HTTPS_PROXY"] = PROXY_URL
        return AsyncOpenAI(**client_kwargs)
    except Exception as e:
        print(f"初始化 AsyncOpenAI 客户端失败: {e}")
        return None


def get_model() -> str | None:
    """获取当前配置的模型名称"""
    return MODEL_NAME if _config_ok else None
