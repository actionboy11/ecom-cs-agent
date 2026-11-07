"""启动装配：FastAPI lifespan 必须真的打开 SQLite 会话库并注入图。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_lifespan_opens_the_sqlite_checkpointer(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(settings, "agent_state_db", str(db_path))

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        # 图已注入：健康检查不应因为“未初始化”而炸
        assert client.get("/api/v1/health").status_code in (200, 503)

    assert db_path.exists(), "lifespan 应创建 SQLite 会话库"
