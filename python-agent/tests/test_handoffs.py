"""P1：坐席转接待办与买家售后进度。"""

from __future__ import annotations

import time

import jwt
import pytest

from app.main import app
from app.session.thread_store import ThreadOwnerStore
from tests.support import TEST_SECRET


def _token(sub: str, user_id: int, role: str = "CUSTOMER") -> str:
    claims = {"sub": sub, "userId": user_id, "role": role, "exp": int(time.time()) + 3600}
    return jwt.encode(claims, TEST_SECRET, algorithm="HS256")


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _agent() -> dict[str, str]:
    return _auth(_token("cs_agent", 4, "CS_AGENT"))


def _handoff(client) -> None:
    chat = client.post(
        "/api/v1/chat",
        json={"thread_id": "t-handoff-inbox", "message": "我要投诉"},
        headers=_auth(_token("buyer_a", 1)),
    )
    assert chat.json()["needs_human"] is True


def test_buyer_cannot_list_handoffs(app_env) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        resp = client.get("/api/v1/handoffs", headers=_auth(_token("buyer_a", 1)))
        assert resp.status_code == 403


def test_agent_sees_pending_handoff_metadata_only(app_env) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        _handoff(client)
        resp = client.get("/api/v1/handoffs", headers=_agent())

        assert resp.status_code == 200
        rows = resp.json()
        row = next(r for r in rows if r["thread_id"] == "t-handoff-inbox")
        assert row["reason"] == "complaint"
        assert row["user_id"] == 1
        # 只返回元数据，不带买家消息正文
        assert "last_message" not in row
        assert "summary" not in row


def test_resume_clears_pending(app_env) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        _handoff(client)
        rows = client.get("/api/v1/handoffs", headers=_agent()).json()
        assert any(r["thread_id"] == "t-handoff-inbox" for r in rows)

        resumed = client.post(
            "/api/v1/threads/t-handoff-inbox/resume",
            json={"approved": True, "note": "已接入"},
            headers=_agent(),
        )
        assert resumed.status_code == 200

        rows = client.get("/api/v1/handoffs", headers=_agent()).json()
        assert all(r["thread_id"] != "t-handoff-inbox" for r in rows)


def test_non_interrupted_thread_is_not_pending(app_env) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        client.post(
            "/api/v1/chat",
            json={"thread_id": "t-normal", "message": "你好"},
            headers=_auth(_token("buyer_a", 1)),
        )
        resp = client.get("/api/v1/handoffs", headers=_agent())
        assert all(row["thread_id"] != "t-normal" for row in resp.json())


def test_legacy_thread_without_pending_flag_is_still_found(app_env) -> None:
    """老库 pending=0 的挂起会话，也要通过最近会话扫描兜住。"""
    import asyncio

    from fastapi.testclient import TestClient

    from app.config import settings

    with TestClient(app) as client:
        _handoff(client)

        async def clear_flag() -> None:
            store = await ThreadOwnerStore.open(settings.agent_state_db)
            await store.clear_pending("t-handoff-inbox")
            await store.close()

        asyncio.run(clear_flag())

        rows = client.get("/api/v1/handoffs", headers=_agent()).json()
        assert any(r["thread_id"] == "t-handoff-inbox" for r in rows)


@pytest.mark.asyncio
async def test_pending_ordering_and_clear(tmp_path) -> None:
    store = await ThreadOwnerStore.open(str(tmp_path / "threads.db"))
    await store.bind("t1", 1)
    await store.bind("t2", 2)
    await store.mark_pending("t1")
    await store.mark_pending("t2")

    pending = await store.list_pending(limit=10)
    assert pending[0]["thread_id"] == "t2"

    await store.clear_pending("t2")
    pending = await store.list_pending(limit=10)
    assert [p["thread_id"] for p in pending] == ["t1"]
    await store.close()
