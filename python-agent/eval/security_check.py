"""安全层检查：4 条越权全部拦截，且 audit_log 有 DENIED 记录。"""

from __future__ import annotations

import json

import httpx

from app.config import settings
from app.tools import business_api

TARGETS = [
    ("query_order", {"order_no": "CS2024005"}, "CS2024005"),
    ("query_logistics", {"order_no": "CS2024005"}, "CS2024005"),
    ("create_after_sales_request", {"order_no": "CS2024005", "type": "REFUND", "reason": "越权测试"}, "CS2024005"),
    ("query_order", {"order_no": "CS2024006"}, "CS2024006"),
]


async def _login(client: httpx.AsyncClient, username: str) -> str:
    resp = await client.post("/api/auth/login", json={"username": username, "password": "demo123"})
    resp.raise_for_status()
    return resp.json()["token"]


async def main() -> None:
    async with httpx.AsyncClient(
        base_url=settings.business_api_base, timeout=10, trust_env=False
    ) as client:
        buyer = await _login(client, "buyer_a")
        agent = await _login(client, "cs_agent")

        blocked = 0
        for name, arguments, _ in TARGETS:
            try:
                await business_api._mcp(name, arguments, buyer)  # noqa: SLF001 - 安全检查脚本
            except business_api.BusinessAPIError as exc:
                if str(exc).startswith(("NOT_FOUND", "DENIED")):
                    blocked += 1

        audit = await client.get(
            "/api/audit", params={"limit": 50}, headers={"Authorization": f"Bearer {agent}"}
        )
        audit.raise_for_status()
        rows = audit.json() if isinstance(audit.json(), list) else audit.json().get("items", [])
        denied = [
            r for r in rows
            if str(r.get("result", "")).upper() == "DENIED"
            and str(r.get("resourceId", "")) in {t[2] for t in TARGETS}
        ]

    result = {
        "cases": len(TARGETS),
        "blocked": blocked,
        "block_rate": round(blocked / len(TARGETS), 3),
        "denied_audits": len(denied),
    }
    print(json.dumps(result, ensure_ascii=False))
    if blocked != len(TARGETS) or not denied:
        raise SystemExit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
