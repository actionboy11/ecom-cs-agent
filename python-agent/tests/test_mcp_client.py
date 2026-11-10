"""S5-3：MCP 客户端（HTTP JSON-RPC）与 JWT 透传。"""

from __future__ import annotations

import json

import httpx
import pytest

from app.tools import business_api
from app.tools.mcp_client import McpError, call_tool


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_calls_tool_with_bearer_token_and_parses_json_text() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization", "")
        payload = json.loads(request.content)
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == "query_order"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "content": [{"type": "text", "text": '{"orderNo":"CS2024001","item":"鞋"}'}]
                },
            },
        )

    result = await call_tool(
        "query_order", {"order_no": "CS2024001"}, "jwt-abc", transport=_transport(handler)
    )

    assert result["orderNo"] == "CS2024001"
    assert seen["auth"] == "Bearer jwt-abc"


@pytest.mark.asyncio
async def test_missing_token_is_rejected_locally() -> None:
    with pytest.raises(McpError) as excinfo:
        await call_tool("query_order", {"order_no": "CS2024001"}, "")
    assert "UNAUTHORIZED" in str(excinfo.value)


@pytest.mark.asyncio
async def test_404_maps_to_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32004, "message": "订单不存在"}}
        )

    with pytest.raises(McpError) as excinfo:
        await call_tool("query_order", {"order_no": "X"}, "jwt", transport=_transport(handler))
    assert str(excinfo.value).startswith("NOT_FOUND")


@pytest.mark.asyncio
async def test_missing_slot_maps_to_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": "缺少订单号"}}
        )

    with pytest.raises(McpError) as excinfo:
        await call_tool("query_order", {}, "jwt", transport=_transport(handler))
    assert str(excinfo.value).startswith("MISSING_SLOT")


@pytest.mark.asyncio
async def test_business_api_wraps_mcp_errors(monkeypatch) -> None:
    async def boom(*_args, **_kwargs):
        raise McpError("NOT_FOUND: 订单不存在")

    monkeypatch.setattr(business_api.mcp_client, "call_tool", boom)

    with pytest.raises(business_api.BusinessAPIError) as excinfo:
        await business_api.get_order("CS2024001", "jwt")
    assert "NOT_FOUND" in str(excinfo.value)
