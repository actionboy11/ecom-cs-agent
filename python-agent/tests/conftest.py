"""共享测试夹具：把模型与状态库都指向本地可控目标。"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from app.config import settings
from tests.support import TEST_SECRET


def pytest_configure(config) -> None:
    """把 pytest 的 basetemp 固定到仓库内：系统临时目录可能不可写，
    默认行为会在工作目录下生成 pytest-of-* 垃圾目录。"""
    if not getattr(config.option, "basetemp", None):
        config.option.basetemp = str(Path(__file__).resolve().parents[1] / ".pytest-tmp" / "basetemp")


@pytest.fixture
def local_tmp() -> Path:
    """工作区内的临时目录。

    Chroma 的 Rust 绑定在 Windows 的系统临时目录下无法打开 SQLite 文件，
    因此测试统一用仓库内目录，避免受 TEMP 权限影响。
    """
    base = Path(__file__).resolve().parents[1] / ".pytest-tmp" / uuid.uuid4().hex
    base.mkdir(parents=True)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)


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
