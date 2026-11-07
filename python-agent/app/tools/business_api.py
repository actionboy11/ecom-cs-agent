"""Java 业务系统客户端。

W1：直接 HTTP 调 Spring Boot 三个接口；
W2：在外层包一个 MCP Server/Client，对外仍是这三个「工具」，Agent 代码不用改。
"""

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings


class BusinessAPIError(RuntimeError):
    """业务系统不可用或返回错误。"""


def _client() -> httpx.AsyncClient:
    # trust_env=False：显式跳过系统代理。
    # 企业网络或本机代理（如 127.0.0.1:12348）会把 http://localhost:8080 也当成外网请求转发，
    # 代理不认识内网地址就回 502 —— 现象是「Java 明明是好的，Agent 却查不到订单」。
    # 排查方式：同一段代码加 trust_env=False 立刻就 200。
    return httpx.AsyncClient(
        base_url=settings.business_api_base,
        timeout=settings.business_api_timeout,
        trust_env=False,
    )


@retry(
    retry=retry_if_exception_type(httpx.TransportError),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.2, max=1),
    reraise=True,
)
async def _request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    try:
        async with _client() as client:
            resp = await client.request(method, path, **kwargs)
    except httpx.TransportError as exc:
        raise BusinessAPIError(f"业务系统连接失败: {exc}") from exc

    if resp.status_code == 404:
        raise BusinessAPIError("未找到对应记录（订单号可能不正确）")
    if resp.status_code >= 400:
        raise BusinessAPIError(f"业务系统错误 {resp.status_code}: {resp.text[:200]}")
    return resp.json()


async def get_order(order_no: str) -> dict[str, Any]:
    return await _request("GET", f"/api/orders/{order_no}")


async def get_logistics(order_no: str) -> dict[str, Any]:
    return await _request("GET", f"/api/logistics/{order_no}")


async def apply_after_sales(order_no: str, as_type: str, reason: str) -> dict[str, Any]:
    """发起售后（REFUND / RETURN / EXCHANGE）。"""
    return await _request(
        "POST", "/api/after-sales", json={"orderNo": order_no, "type": as_type, "reason": reason}
    )


async def get_product(sku: str) -> dict[str, Any]:
    return await _request("GET", f"/api/products/{sku}")


async def healthy() -> bool:
    try:
        async with _client() as client:
            resp = await client.get("/api/health", timeout=2)
            return resp.status_code == 200
    except httpx.HTTPError:
        return False
