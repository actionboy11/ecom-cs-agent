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
async def test_403_maps_to_denied_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32003, "message": "售后只能由买家发起"}}
        )

    with pytest.raises(McpError) as excinfo:
        await call_tool("create_after_sales_request", {}, "jwt", transport=_transport(handler))
    assert str(excinfo.value).startswith("DENIED")


@pytest.mark.asyncio
async def test_top_level_error_on_200_is_not_silently_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Method not found"}}
        )

    with pytest.raises(McpError):
        await call_tool("query_order", {"order_no": "X"}, "jwt", transport=_transport(handler))


@pytest.mark.asyncio
async def test_codes_are_not_double_prefixed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"jsonrpc": "2.0", "id": 1,
                  "error": {"code": -32602, "message": "INVALID_INPUT: 不支持的售后类型"}},
        )

    with pytest.raises(McpError) as excinfo:
        await call_tool("create_after_sales_request", {}, "jwt", transport=_transport(handler))
    assert str(excinfo.value) == "INVALID_INPUT: 不支持的售后类型"


@pytest.mark.asyncio
async def test_tool_node_reads_token_from_config(monkeypatch) -> None:
    from app.graph import nodes

    captured: dict[str, str] = {}

    async def fake_get_order(order_no, token):
        captured["token"] = token
        return {"orderNo": order_no}

    monkeypatch.setattr(nodes.business_api, "get_order", fake_get_order)

    result = await nodes.tool_node(
        {"messages": [], "thread_id": "t", "intent": "order_query", "order_no": "CS2024001"},
        {"configurable": {"thread_id": "t", "auth_token": "jwt-from-config"}},
    )

    assert captured["token"] == "jwt-from-config"
    assert result["tool_result"]["orderNo"] == "CS2024001"


def test_unauthorized_reply_asks_for_relogin() -> None:
    from app.graph.nodes import _template_reply

    reply = _template_reply(
        {"intent": "order_query", "tool_result": {"error": "UNAUTHORIZED: 令牌无效或已过期"}}
    )
    assert "重新登录" in reply


@pytest.mark.asyncio
async def test_business_api_wraps_mcp_errors(monkeypatch) -> None:
    async def boom(*_args, **_kwargs):
        raise McpError("NOT_FOUND: 订单不存在")

    monkeypatch.setattr(business_api.mcp_client, "call_tool", boom)

    with pytest.raises(business_api.BusinessAPIError) as excinfo:
        await business_api.get_order("CS2024001", "jwt")
    assert "NOT_FOUND" in str(excinfo.value)
