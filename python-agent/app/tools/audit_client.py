"""向 Java 内部审计接口上报事件（Agent 侧越权等）。

安全约束：
- 只传元数据（谁、对哪个资源、做了什么、结果、路径），不传对话正文；
- 令牌来自 `INTERNAL_AUDIT_TOKEN`，为空则不上报（开发环境静默跳过）；
- 上报失败只记日志，绝不影响主流程（与 Java 的 recordQuietly 同语义）。
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def record_thread_denied(
    *, actor: str, role: str, thread_id: str, path: str, reason: str
) -> None:
    token = settings.internal_audit_token
    if not token:
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
    try:
        async with httpx.AsyncClient(
            base_url=settings.business_api_base, timeout=1.5, trust_env=False
        ) as client:
            await client.post(
                "/api/internal/audit", json=payload, headers={"X-Internal-Token": token}
            )
    except httpx.HTTPError as exc:
        logger.warning("越权审计上报失败（已忽略）: %s", str(exc)[:200])
