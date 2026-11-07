"""启动装配：FastAPI lifespan 必须真的打开 SQLite 会话库、注入图，并清理过期会话。"""

from __future__ import annotations

import asyncio
import sqlite3

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.session.thread_store import ThreadOwnerStore


def test_lifespan_opens_the_sqlite_checkpointer(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(settings, "agent_state_db", str(db_path))

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        # 图已注入：健康检查不应因为“未初始化”而炸
        assert client.get("/api/v1/health").status_code in (200, 503)

    assert db_path.exists(), "lifespan 应创建 SQLite 会话库"


async def _seed_expired_owner(db_path: str) -> None:
    store = await ThreadOwnerStore.open(db_path)
    await store.bind("t-expired", 1)
    await store.close()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE thread_owner SET updated_at = datetime('now', '-40 days') WHERE thread_id = 't-expired'"
    )
    conn.commit()
    conn.close()


def test_lifespan_purges_expired_threads(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "state.db"
    asyncio.run(_seed_expired_owner(str(db_path)))
    monkeypatch.setattr(settings, "agent_state_db", str(db_path))

    with TestClient(app):
        pass

    conn = sqlite3.connect(db_path)
    owners = [r[0] for r in conn.execute("SELECT thread_id FROM thread_owner")]
    conn.close()
    assert owners == [], "启动时应清理超过保留期的会话"
