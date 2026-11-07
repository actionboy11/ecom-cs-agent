"""共享测试夹具：把模型与状态库都指向本地可控目标。"""

from __future__ import annotations

import pytest

from app.config import settings

TEST_SECRET = "test-secret-key-32-bytes-long!!!"


@pytest.fixture
def offline_llm(monkeypatch):
    """模型指向不可达地址：节点走关键词兜底 + 模板回复，不发真实请求。"""
    monkeypatch.setattr(settings, "deepseek_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "qwen_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "deepseek_api_key", "test")
    monkeypatch.setattr(settings, "qwen_api_key", "test")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.5)


@pytest.fixture
def app_env(tmp_path, monkeypatch, offline_llm):
    """独立状态库 + 固定 JWT 密钥。"""
    monkeypatch.setattr(settings, "agent_state_db", str(tmp_path / "state.db"))
    monkeypatch.setattr(settings, "jwt_secret", TEST_SECRET)
    return tmp_path
