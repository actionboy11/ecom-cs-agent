"""业务系统工具：经 MCP 调用 Java 侧（订单 / 物流 / 售后 / 商品）。

工具名与参数遵循 SPEC §7.1；身份通过调用方传入的 JWT 透传。
UNAVAILABLE 按 SPEC §7.2 重试一次，其余错误直接上抛。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings
from app.tools import mcp_client
from app.tools.mcp_client import McpError

logger = logging.getLogger(__name__)


class BusinessAPIError(RuntimeError):
    """业务系统不可用或返回错误（message 带 SPEC §7.2 错误码前缀）。"""


def _client() -> httpx.AsyncClient:
    # trust_env=False：显式跳过系统代理（代理会把 localhost 也转发，表现为 502）
    return httpx.AsyncClient(
        base_url=settings.business_api_base,
        timeout=settings.business_api_timeout,
        trust_env=False,
    )


async def _mcp(name: str, arguments: dict[str, Any], token: str) -> Any:
    for attempt in (1, 2):
        try:
            return await mcp_client.call_tool(name, arguments, token)
        except McpError as exc:
            message = str(exc)
            if attempt == 1 and message.startswith(("UNAVAILABLE", "TIMEOUT")):
                await asyncio.sleep(0.2)
                continue
            logger.warning("MCP 工具调用失败 %s: %s", name, message[:200])
            raise BusinessAPIError(message) from exc
    raise BusinessAPIError("UNAVAILABLE: 重试后仍失败")  # pragma: no cover


async def get_order(order_no: str, token: str) -> dict[str, Any]:
    return await _mcp("query_order", {"order_no": order_no}, token)


async def get_logistics(order_no: str, token: str) -> dict[str, Any]:
    return await _mcp("query_logistics", {"order_no": order_no}, token)


async def apply_after_sales(
    order_no: str, as_type: str, reason: str, token: str
) -> dict[str, Any]:
    """发起售后（REFUND / RETURN / EXCHANGE）。"""
    return await _mcp(
        "create_after_sales_request",
        {"order_no": order_no, "type": as_type, "reason": reason},
        token,
    )


async def get_product(sku: str, token: str = "") -> dict[str, Any]:
    """商品查询也走 MCP（SPEC §7.1 `get_product_info`）。"""
    return await _mcp("get_product_info", {"sku": sku}, token)


async def healthy() -> bool:
    try:
        async with _client() as client:
            resp = await client.get("/api/health", timeout=2)
            return resp.status_code == 200
    except httpx.HTTPError:
        return False
