"""S7-1：工作台 API 客户端（UI 只做编排，逻辑在这里可测）。"""

from __future__ import annotations

import httpx
import pytest

from ui.api_client import WorkbenchApi, WorkbenchError


def _api(handler) -> WorkbenchApi:
    return WorkbenchApi(
        java_base="http://java.test",
        agent_base="http://agent.test",
        transport=httpx.MockTransport(handler),
    )


def test_login_sends_credentials_and_returns_token() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"token": "jwt", "role": "CS_AGENT", "userId": 4})

    result = _api(handler).login("cs_agent", "demo123")

    assert result["token"] == "jwt"
    assert "cs_agent" in seen["body"]
    assert seen["url"].endswith("/api/auth/login")


def test_chat_uses_bearer_token_and_thread() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"reply": "已为您查询", "needs_human": False})

    reply = _api(handler).chat("jwt", "t-1", "CS2024001 到哪了")

    assert reply["reply"] == "已为您查询"
    assert seen["auth"] == "Bearer jwt"
    assert "t-1" in seen["body"]


def test_login_failure_is_a_workbench_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": "INVALID_CREDENTIALS", "message": "用户名或密码错误"}
        )

    with pytest.raises(WorkbenchError):
        _api(handler).login("buyer_a", "wrong")


def test_agent_review_calls_review_endpoint() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"status": "APPROVED"})

    result = _api(handler).review("jwt", "AS20261101000001", True, "同意")

    assert result["status"] == "APPROVED"
    assert "/api/after-sales/AS20261101000001/review" in seen["url"]
    assert "APPROVED" not in seen["body"]
    assert "true" in seen["body"]


def test_resume_posts_to_thread_endpoint() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"reply": "已恢复", "needs_human": False})

    reply = _api(handler).resume("jwt", "t-9", True, "同意")

    assert reply["reply"] == "已恢复"
    assert "/api/v1/threads/t-9/resume" in seen["url"]
    assert "true" in seen["body"]


def test_handoffs_and_my_after_sales_endpoints() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        if request.url.path.endswith("/handoffs"):
            return httpx.Response(200, json=[{"thread_id": "t-1", "reason": "complaint"}])
        return httpx.Response(200, json=[{"requestNo": "AS1", "status": "PENDING"}])

    api = _api(handler)

    assert api.handoffs("jwt")[0]["thread_id"] == "t-1"
    assert "/api/v1/handoffs" in seen["path"]
    assert api.my_after_sales("jwt")[0]["requestNo"] == "AS1"
    assert seen["path"].endswith("/api/after-sales")


def test_network_error_becomes_workbench_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(WorkbenchError):
        _api(handler).handoffs("jwt")


def test_pending_and_audit_hit_java_endpoints() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "after-sales" in str(request.url):
            return httpx.Response(200, json=[{"requestNo": "AS1"}])
        return httpx.Response(200, json=[{"action": "LOGIN"}])

    api = _api(handler)
    assert api.pending_after_sales("jwt")[0]["requestNo"] == "AS1"
    assert api.audit("jwt", limit=5)[0]["action"] == "LOGIN"
