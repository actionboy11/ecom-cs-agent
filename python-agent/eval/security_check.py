"""安全层检查：4 条越权（他人订单）全部拦截，且**本次运行新增**的审计里有对应 DENIED。"""

from __future__ import annotations

import json

import httpx

from app.config import settings
from app.tools import business_api

# 都是 buyer_b 的订单（评测以 buyer_a 身份发起）
TARGETS = [
    ("query_order", "CS2024005"),
    ("query_logistics", "CS2024005"),
    ("create_after_sales_request", "CS2024006"),
    ("query_order", "CS2024007"),
]


def evaluate(blocked: int, new_denied: set[str], targets: list[tuple[str, str]]) -> dict:
    """拦截数必须等于用例数，且每条目标资源都有**新增**的 DENIED 审计。"""
    expected = {order for _, order in targets}
    covered = new_denied & expected
    return {
        "cases": len(targets),
        "blocked": blocked,
        "block_rate": round(blocked / len(targets), 3),
        "denied_audits": len(covered),
        "audit_covered": sorted(covered),
        "ok": blocked == len(targets) and covered == expected,
    }


async def _login(client: httpx.AsyncClient, username: str) -> str:
    resp = await client.post("/api/auth/login", json={"username": username, "password": "demo123"})
    resp.raise_for_status()
    return resp.json()["token"]


async def _audit_ids(client: httpx.AsyncClient, token: str) -> set[int]:
    resp = await client.get(
        "/api/audit", params={"limit": 100}, headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    payload = resp.json()
    rows = payload if isinstance(payload, list) else payload.get("items", [])
    return {int(r["id"]) for r in rows if "id" in r}


async def run_security(client: httpx.AsyncClient, buyer: str, agent: str) -> dict:
    baseline = await _audit_ids(client, agent)

    blocked = 0
    for name, order_no in TARGETS:
        try:
            if name == "query_order":
                await business_api.get_order(order_no, buyer)
            elif name == "query_logistics":
                await business_api.get_logistics(order_no, buyer)
            else:
                await business_api.apply_after_sales(order_no, "REFUND", "越权测试", buyer)
        except business_api.BusinessAPIError as exc:
            if str(exc).startswith(("NOT_FOUND", "DENIED")):
                blocked += 1

    resp = await client.get(
        "/api/audit", params={"limit": 100}, headers={"Authorization": f"Bearer {agent}"}
    )
    resp.raise_for_status()
    payload = resp.json()
    rows = payload if isinstance(payload, list) else payload.get("items", [])
    new_denied = {
        str(r.get("resourceId", ""))
        for r in rows
        if int(r.get("id", -1)) not in baseline and str(r.get("result", "")).upper() == "DENIED"
    }
    return evaluate(blocked, new_denied, TARGETS)


async def check() -> dict:
    """供三层评测调用：自己管理 HTTP 客户端。"""
    async with httpx.AsyncClient(
        base_url=settings.business_api_base, timeout=10, trust_env=False
    ) as client:
        buyer = await _login(client, "buyer_a")
        agent = await _login(client, "cs_agent")
        return await run_security(client, buyer, agent)


async def main() -> None:
    result = await check()
    print(json.dumps(result, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
