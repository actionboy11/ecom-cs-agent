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


def test_buyer_cannot_list_handoffs(app_env) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        resp = client.get("/api/v1/handoffs", headers=_auth(_token("buyer_a", 1)))
        assert resp.status_code == 403


def test_agent_sees_pending_handoff(app_env) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        chat = client.post(
            "/api/v1/chat",
            json={"thread_id": "t-handoff-inbox", "message": "我要投诉"},
            headers=_auth(_token("buyer_a", 1)),
        )
        assert chat.json()["needs_human"] is True

        resp = client.get("/api/v1/handoffs", headers=_agent())
        assert resp.status_code == 200
        rows = resp.json()
        ids = {row["thread_id"] for row in rows}
        assert "t-handoff-inbox" in ids
        row = next(r for r in rows if r["thread_id"] == "t-handoff-inbox")
        assert row["reason"] == "complaint"
        assert row["user_id"] == 1


def test_handoffs_empty_when_no_interrupt(app_env) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        client.post(
            "/api/v1/chat",
            json={"thread_id": "t-normal", "message": "你好"},
            headers=_auth(_token("buyer_a", 1)),
        )
        resp = client.get("/api/v1/handoffs", headers=_agent())
        assert resp.status_code == 200
        assert all(row["thread_id"] != "t-normal" for row in resp.json())


@pytest.mark.asyncio
async def test_list_recent_returns_newest_first(tmp_path) -> None:
    store = await ThreadOwnerStore.open(str(tmp_path / "threads.db"))
    await store.bind("t1", 1)
    await store.bind("t2", 2)
    await store.touch("t1")

    rows = await store.list_recent(limit=10)

    assert next(r["thread_id"] for r in rows) == "t1"
    await store.close()
