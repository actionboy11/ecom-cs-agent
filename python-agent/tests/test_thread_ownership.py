"""S3-2：会话归属。

规则（SPEC §2 / ADR-0001）：
- 首次消息把 thread 绑定到当前用户；
- 买家续别人的 thread → 404（与不存在同口径）；
- 坐席审批恢复不受归属限制（SPEC §2 的 resume 行）。
"""

from __future__ import annotations

import time

import jwt
from fastapi.testclient import TestClient

from app.main import app
from tests.support import TEST_SECRET


def _token(sub: str, user_id: int, role: str = "CUSTOMER", exp_delta: int | None = 3600) -> str:
    claims: dict[str, object] = {"sub": sub, "userId": user_id, "role": role}
    if exp_delta is not None:
        claims["exp"] = int(time.time()) + exp_delta
    return jwt.encode(claims, TEST_SECRET, algorithm="HS256")


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _chat(client: TestClient, thread_id: str, token: str) -> int:
    return client.post(
        "/api/v1/chat",
        json={"thread_id": thread_id, "message": "退货政策几天"},
        headers=_auth(token),
    ).status_code


def test_first_message_binds_and_owner_can_continue(app_env) -> None:
    with TestClient(app) as client:
        buyer_a = _token("buyer_a", 1)
        assert _chat(client, "t-owned", buyer_a) == 200
        assert _chat(client, "t-owned", buyer_a) == 200


def test_other_buyer_cannot_continue_someone_elses_thread(app_env) -> None:
    with TestClient(app) as client:
        buyer_a = _token("buyer_a", 1)
        buyer_b = _token("buyer_b", 2)
        assert _chat(client, "t-secret", buyer_a) == 200

        resp = client.post(
            "/api/v1/chat",
            json={"thread_id": "t-secret", "message": "我也来看看"},
            headers=_auth(buyer_b),
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "会话不存在"


def test_agent_cannot_take_over_a_buyers_conversation(app_env) -> None:
    with TestClient(app) as client:
        assert _chat(client, "t-buyer", _token("buyer_a", 1)) == 200
        assert _chat(client, "t-buyer", _token("cs_agent", 4, "CS_AGENT")) == 404


def test_buyer_cannot_resume_someone_elses_thread(app_env) -> None:
    with TestClient(app) as client:
        assert _chat(client, "t-handoff", _token("buyer_a", 1)) == 200
        resp = client.post(
            "/api/v1/threads/t-handoff/resume",
            json={"approved": True},
            headers=_auth(_token("buyer_b", 2)),
        )
        # 恢复是坐席权限：买家按越权处理，统一 404（不区分会话归属）
        assert resp.status_code == 404


def test_agent_may_resume_for_approval(app_env) -> None:
    with TestClient(app) as client:
        assert _chat(client, "t-agent", _token("buyer_a", 1)) == 200
        resp = client.post(
            "/api/v1/threads/t-agent/resume",
            json={"approved": True},
            headers=_auth(_token("cs_agent", 4, "ROLE_CS_AGENT")),
        )
        # 没有待审任务时返回 409；关键是不能被归属规则挡住（404）或报错（5xx）
        assert resp.status_code in (200, 409)


def test_missing_or_invalid_token_is_rejected(app_env) -> None:
    with TestClient(app) as client:
        assert client.post("/api/v1/chat", json={"thread_id": "t", "message": "你好"}).status_code == 401
        bad = client.post(
            "/api/v1/chat",
            json={"thread_id": "t", "message": "你好"},
            headers=_auth("not-a-jwt"),
        )
        assert bad.status_code == 401


def test_token_without_exp_is_rejected(app_env) -> None:
    """没有过期时间的令牌等于永久凭证，必须拒绝（SPEC §6.1）。"""
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/chat",
            json={"thread_id": "t-noexp", "message": "你好"},
            headers=_auth(_token("buyer_a", 1, exp_delta=None)),
        )
        assert resp.status_code == 401


def test_expired_token_is_rejected(app_env) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/chat",
            json={"thread_id": "t-exp", "message": "你好"},
            headers=_auth(_token("buyer_a", 1, exp_delta=-60)),
        )
        assert resp.status_code == 401


def test_stream_endpoint_requires_auth(app_env) -> None:
    with TestClient(app) as client:
        resp = client.post("/api/v1/chat/stream", json={"thread_id": "t", "message": "你好"})
        assert resp.status_code == 401


def test_unknown_thread_resume_is_404_for_buyer(app_env) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/threads/never-existed/resume",
            json={"approved": True},
            headers=_auth(_token("buyer_a", 1)),
        )
        assert resp.status_code == 404


def test_owner_cannot_resume_their_own_handoff(app_env) -> None:
    """买家不能自己批准转人工：否则传 approved=true 就绕过人工审批。"""
    with TestClient(app) as client:
        buyer_a = _token("buyer_a", 1)
        chat = client.post(
            "/api/v1/chat",
            json={"thread_id": "t-owner-resume", "message": "我要投诉"},
            headers=_auth(buyer_a),
        )
        assert chat.status_code == 200
        assert chat.json()["needs_human"] is True

        resumed = client.post(
            "/api/v1/threads/t-owner-resume/resume",
            json={"approved": True},
            headers=_auth(buyer_a),
        )
        # 越权统一 404（ADR-0001），而不是 403
        assert resumed.status_code == 404


def test_resume_denial_is_audited(app_env, monkeypatch) -> None:
    """买家越权调用 resume 也要写 DENIED 审计（与订单类越权同口径）。"""
    import app.api.routes as routes

    calls: list[dict] = []

    async def fake_record(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(routes.audit_client, "record_thread_denied", fake_record)

    with TestClient(app) as client:
        assert _chat(client, "t-resume-audit", _token("buyer_a", 1)) == 200
        resp = client.post(
            "/api/v1/threads/t-resume-audit/resume",
            json={"approved": True},
            headers=_auth(_token("buyer_a", 1)),
        )
        assert resp.status_code == 404

    assert calls, "越权恢复应上报 DENIED 审计"
    assert calls[0]["reason"] == "resume_requires_agent"
    assert calls[0]["thread_id"] == "t-resume-audit"


def test_agent_can_reject_handoff(app_env) -> None:
    with TestClient(app) as client:
        chat = client.post(
            "/api/v1/chat",
            json={"thread_id": "t-reject", "message": "我要投诉"},
            headers=_auth(_token("buyer_a", 1)),
        )
        assert chat.json()["needs_human"] is True

        resp = client.post(
            "/api/v1/threads/t-reject/resume",
            json={"approved": False, "note": "已电话沟通"},
            headers=_auth(_token("cs_agent", 4, "CS_AGENT")),
        )
        assert resp.status_code == 200
        assert resp.json()["needs_human"] is False


def test_stream_rejects_other_users_thread(app_env) -> None:
    with TestClient(app) as client:
        assert _chat(client, "t-stream", _token("buyer_a", 1)) == 200
        resp = client.post(
            "/api/v1/chat/stream",
            json={"thread_id": "t-stream", "message": "继续"},
            headers=_auth(_token("buyer_b", 2)),
        )
        assert resp.status_code == 404


def test_legacy_thread_without_owner_cannot_be_claimed(app_env) -> None:
    """#13 之前的会话没有归属记录：不能被任何人凭 thread_id 直接接管。"""
    import asyncio

    from langchain_core.messages import HumanMessage

    from app.graph.builder import get_graph

    with TestClient(app) as client:
        graph = get_graph()
        asyncio.run(
            graph.aupdate_state(
                {"configurable": {"thread_id": "t-legacy"}},
                {"messages": [HumanMessage(content="升级前的历史会话")]},
            )
        )
        assert _chat(client, "t-legacy", _token("buyer_a", 1)) == 404


def test_cross_user_access_reports_denied_to_audit(app_env, monkeypatch) -> None:
    """Agent 侧越权要写 MySQL 审计；这里断言确实向上报了（不校验远端落库）。"""
    import app.api.routes as routes

    calls: list[dict] = []

    async def fake_record(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(routes.audit_client, "record_thread_denied", fake_record)

    with TestClient(app) as client:
        assert _chat(client, "t-audit", _token("buyer_a", 1)) == 200
        assert _chat(client, "t-audit", _token("buyer_b", 2)) == 404

    assert calls, "越权时应上报 DENIED 审计"
    assert calls[0]["thread_id"] == "t-audit"
    assert calls[0]["reason"] == "not_owner"
    assert calls[0]["actor"] == "buyer_b"


def test_empty_thread_id_is_rejected(app_env) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/chat",
            json={"thread_id": "", "message": "你好"},
            headers=_auth(_token("buyer_a", 1)),
        )
        assert resp.status_code == 422
