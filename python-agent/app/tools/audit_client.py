"""向 Java 内部审计接口上报事件（Agent 侧越权等）。

安全约束：
- 只传元数据（谁、对哪个资源、做了什么、结果、路径），不传对话正文；
- 令牌来自 `INTERNAL_AUDIT_TOKEN`，为空则不上报（开发环境静默跳过）；
- 非 2xx 会记日志（不静默成功）；上报失败绝不影响主流程；
- 同一 (user, thread) 60 秒内只报一次，避免被任意 thread_id 刷爆审计表。
"""

from __future__ import annotations

import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_DEDUPE: dict[tuple[str, str], float] = {}
_DEDUPE_WINDOW_SECONDS = 60.0


def _should_report(user: str, thread_id: str) -> bool:
    key = (user, thread_id)
    now = time.monotonic()
    last = _DEDUPE.get(key)
    if last is not None and now - last < _DEDUPE_WINDOW_SECONDS:
        return False
    _DEDUPE[key] = now
    return True


async def record_thread_denied(
    *,
    actor: str,
    role: str,
    thread_id: str,
    path: str,
    reason: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    token = settings.internal_audit_token
    if not token or not _should_report(actor, thread_id):
        return

    payload = {
        "actor": actor,
        "actorRole": role,
        "action": "THREAD_ACCESS",
        "resourceType": "THREAD",
        "resourceId": thread_id,
        "result": "DENIED",
        "path": path,
        "detail": {"reason": reason},
    }
    client_kwargs: dict = {
        "base_url": settings.business_api_base,
        "timeout": 0.5,
        "trust_env": False,
    }
    if transport is not None:
        client_kwargs["transport"] = transport
    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.post(
                "/api/internal/audit", json=payload, headers={"X-Internal-Token": token}
            )
        if resp.status_code >= 400:
            logger.warning("越权审计被拒绝 %s: %s", resp.status_code, resp.text[:200])
    except httpx.HTTPError as exc:
        logger.warning("越权审计上报失败（已忽略）: %s", str(exc)[:200])
