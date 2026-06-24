"""测试 - 配置管理"""

import os
from unittest.mock import patch

import pytest

from shop_analyzer import config


def test_check_config_missing(monkeypatch):
    """缺少环境变量时 check_config 应返回 False"""
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL_NAME", raising=False)
    # 重新加载会继承模块的全局变量，需要打补丁
    with patch.object(config, "_config_ok", False):
        assert config.check_config() is False


def test_check_config_present(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.com/v1/")
    monkeypatch.setenv("OPENAI_MODEL_NAME", "gpt-4o")
    with patch.object(config, "_config_ok", True):
        assert config.check_config() is True


def test_build_client_none():
    with patch.object(config, "_config_ok", False):
        assert config.build_client() is None


def test_get_model_none():
    with patch.object(config, "_config_ok", False):
        assert config.get_model() is None


def test_get_model_ok(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL_NAME", "gpt-4o")
    with patch.object(config, "MODEL_NAME", "gpt-4o"):
        with patch.object(config, "_config_ok", True):
            assert config.get_model() == "gpt-4o"
