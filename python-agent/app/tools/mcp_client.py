"""MCP 客户端：按 JSON-RPC 2.0 调用 Java 侧 `POST /mcp`。

身份随每次调用以 `Authorization: Bearer <jwt>` 透传；Java 侧从登录上下文注入用户，
工具参数里没有 user_id，模型无法伪造身份。

失败统一转成带 SPEC §7.2 错误码前缀的 `McpError`：
UNAUTHORIZED / FORBIDDEN / NOT_FOUND / MISSING_SLOT / INVALID_INPUT / UNAVAILABLE。
"""

from __future__ import annotations

import itertools
import json
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings

_request_id = itertools.count(1)

_CODES = ("UNAUTHORIZED", "FORBIDDEN", "NOT_FOUND", "MISSING_SLOT", "INVALID_INPUT", "UNAVAILABLE")


class McpError(RuntimeError):
    """MCP 调用失败，message 带 SPEC §7.2 的错误码前缀。"""


def _coded(code: str, message: str) -> McpError:
    """避免 Java 与 Python 重复加前缀（`INVALID_INPUT: INVALID_INPUT: ...`）。"""
    text = str(message).strip()
    if text.startswith(tuple(f"{c}:" for c in _CODES)):
        return McpError(text)
    return McpError(f"{code}: {text}")


def _message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200]
    if not isinstance(body, dict):
        return str(body)[:200]
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or body)[:200]
    if isinstance(error, str):
        return str(body.get("message") or error)[:200]
    return str(body)[:200]


def _parse(resp: httpx.Response) -> Any:
    if resp.status_code == 401:
        raise _coded("UNAUTHORIZED", "令牌无效或已过期")
    if resp.status_code == 403:
        raise _coded("DENIED", _message(resp))
    if resp.status_code == 404:
        raise _coded("NOT_FOUND", _message(resp))
    if resp.status_code >= 400:
        try:
            body = resp.json()
        except ValueError:
            body = {}
        code = (body.get("error") or {}).get("code") if isinstance(body, dict) else None
        if code == -32001:
            raise _coded("MISSING_SLOT", _message(resp))
        if code == -32602:
            raise _coded("INVALID_INPUT", _message(resp))
        if code == -32002:
            raise _coded("UNAVAILABLE", _message(resp))
        raise _coded("UNAVAILABLE", f"HTTP {resp.status_code} {_message(resp)}")

    body = resp.json()
    if not isinstance(body, dict):
        raise _coded("UNAVAILABLE", "响应格式异常")
    if body.get("error"):
        code = (body.get("error") or {}).get("code")
        if code == -32004:
            raise _coded("NOT_FOUND", _message(resp))
        if code == -32001:
            raise _coded("MISSING_SLOT", _message(resp))
        if code == -32602:
            raise _coded("INVALID_INPUT", _message(resp))
        raise _coded("UNAVAILABLE", _message(resp))
    result = body.get("result") or {}
    if result.get("isError"):
        text = (result.get("content") or [{}])[0].get("text", "工具执行失败")
        raise _coded("UNAVAILABLE", text)

    content = result.get("content") or []
    if not content:
        return None
    text = content[0].get("text", "")
    try:
        return json.loads(text)
    except ValueError:
        return text


@retry(
    retry=retry_if_exception_type(httpx.TransportError),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.2, max=1),
    reraise=True,
)
async def call_tool(
    name: str,
    arguments: dict[str, Any],
    token: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Any:
    """调用 MCP 工具并返回解析后的结果（工具返回 JSON 文本，这里解一层）。"""
    if not token:
        raise McpError("UNAUTHORIZED: 缺少登录令牌")

    payload = {
        "jsonrpc": "2.0",
        "id": next(_request_id),
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    headers = {"Authorization": f"Bearer {token}"}
    client_kwargs: dict[str, Any] = {
        "base_url": settings.business_api_base,
        "timeout": settings.business_api_timeout,
        "trust_env": False,
    }
    if transport is not None:
        client_kwargs["transport"] = transport

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.post("/mcp", json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise McpError(f"TIMEOUT: 业务系统超时: {exc}") from exc
    except httpx.TransportError as exc:
        raise McpError(f"UNAVAILABLE: 业务系统连接失败: {exc}") from exc

    return _parse(resp)
