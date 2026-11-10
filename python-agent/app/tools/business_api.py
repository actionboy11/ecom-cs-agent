"""业务系统工具：经 MCP 调用 Java 侧（产品查询仍走公开 REST）。

工具名与参数遵循 SPEC §7.1；身份通过调用方传入的 JWT 透传。
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.tools import mcp_client
from app.tools.mcp_client import McpError


class BusinessAPIError(RuntimeError):
    """业务系统不可用或返回错误。"""


def _client() -> httpx.AsyncClient:
    # trust_env=False：显式跳过系统代理（代理会把 localhost 也转发，表现为 502）
    return httpx.AsyncClient(
        base_url=settings.business_api_base,
        timeout=settings.business_api_timeout,
        trust_env=False,
    )


async def _mcp(name: str, arguments: dict[str, Any], token: str) -> Any:
    try:
        return await mcp_client.call_tool(name, arguments, token)
    except McpError as exc:
        raise BusinessAPIError(str(exc)) from exc


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


@retry(
    retry=retry_if_exception_type(httpx.TransportError),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.2, max=1),
    reraise=True,
)
async def get_product(sku: str) -> dict[str, Any]:
    """商品查询是公开数据，仍走 REST（MCP 工具清单里暂未包含）。"""
    try:
        async with _client() as client:
            resp = await client.get(f"/api/products/{sku}")
    except httpx.TransportError as exc:
        raise BusinessAPIError(f"业务系统连接失败: {exc}") from exc
    if resp.status_code == 404:
        raise BusinessAPIError("未找到对应商品")
    if resp.status_code >= 400:
        raise BusinessAPIError(f"业务系统错误 {resp.status_code}: {resp.text[:200]}")
    return resp.json()


async def healthy() -> bool:
    try:
        async with _client() as client:
            resp = await client.get("/api/health", timeout=2)
            return resp.status_code == 200
    except httpx.HTTPError:
        return False
