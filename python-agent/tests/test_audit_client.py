"""S6-3：Agent → Java 内部审计上报的载荷与去重。"""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import settings
from app.tools.audit_client import record_thread_denied


@pytest.mark.asyncio
async def test_payload_carries_metadata_only(monkeypatch) -> None:
    monkeypatch.setattr(settings, "internal_audit_token", "test-token")
    monkeypatch.setattr(settings, "business_api_base", "http://java.test")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["token"] = request.headers.get("x-internal-token")
        return httpx.Response(200, json={"status": "recorded"})

    await record_thread_denied(
        actor="buyer_b",
        role="CUSTOMER",
        thread_id="t-payload",
        path="/api/v1/chat",
        reason="not_owner",
        transport=httpx.MockTransport(handler),
    )

    body = seen["body"]
    assert body["action"] == "THREAD_ACCESS"
    assert body["resourceType"] == "THREAD"
    assert body["result"] == "DENIED"
    assert body["path"] == "/api/v1/chat"
    assert body["detail"] == {"reason": "not_owner"}
    assert seen["token"] == "test-token"
    # 不携带对话正文/密码/令牌
    dumped = json.dumps(body)
    assert "message" not in dumped
    assert "password" not in dumped
    assert "Authorization" not in dumped


@pytest.mark.asyncio
async def test_repeated_denials_are_deduped(monkeypatch) -> None:
    monkeypatch.setattr(settings, "internal_audit_token", "test-token")
    monkeypatch.setattr(settings, "business_api_base", "http://java.test")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"status": "recorded"})

    for _ in range(3):
        await record_thread_denied(
            actor="buyer_b",
            role="CUSTOMER",
            thread_id="t-dedupe",
            path="/api/v1/chat",
            reason="not_owner",
            transport=httpx.MockTransport(handler),
        )

    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_skips_when_token_missing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "internal_audit_token", "")

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - 不应被调用
        raise AssertionError("没有令牌时不应发起上报")

    await record_thread_denied(
        actor="buyer_b",
        role="CUSTOMER",
        thread_id="t-no-token",
        path="/api/v1/chat",
        reason="not_owner",
        transport=httpx.MockTransport(handler),
    )
