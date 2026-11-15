"""15 条 ReAct 工具选择评测：检查 trace 中是否出现期望工具/写确认。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

CASES = [
    ("r01", "我的鞋想退货", {"find_my_orders"}, False),
    ("r02", "CS2024105 到哪了", {"query_logistics"}, False),
    ("r03", "拆封的鞋还能退吗", {"search_policy"}, False),
    ("r04", "我的耳机到哪了", {"find_my_orders"}, False),
    ("r05", "背包有货吗", {"get_product", "find_my_orders"}, False),
    ("r06", "我要退 CS2024105", set(), True),
    ("r07", "CS2024102 物流", {"query_logistics"}, False),
    ("r08", "耳机多少钱", {"find_my_orders", "get_product"}, False),
    ("r09", "我的杯子想退", {"find_my_orders"}, False),
    ("r10", "CS2024103 订单详情", {"query_order"}, False),
    ("r11", "赠送的耳机坏了", set(), True),
    ("r12", "行李箱降价能价保吗", {"search_policy"}, False),
    ("r13", "镜子的订单", {"find_my_orders"}, False),
    ("r14", "我的鞋到哪了", {"find_my_orders"}, False),
    ("r15", "退款要多久到账", {"search_policy"}, False),
    ("r16", "我要退货 CS2024105，鞋子开胶", set(), True),
    ("r17", "我要换货 CS2024101，换43码", set(), True),
]


async def main() -> None:
    async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
        token = (
            await client.post(
                "http://localhost:8080/api/auth/login",
                json={"username": "buyer_test", "password": "demo123"},
            )
        ).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        rows = []
        for cid, message, expected, write in CASES:
            thread = f"react-eval-{cid}-{int(asyncio.get_running_loop().time() * 1000)}"
            resp = await client.post(
                "http://localhost:8000/api/v1/chat",
                json={"thread_id": thread, "message": message},
                headers=headers,
            )
            data = resp.json()
            tools = {item.get("tool") for item in (data.get("tool_trace") or []) if item.get("tool")}
            interrupt = data.get("interrupt") or {}
            if write:
                wanted_action = {"r06": "refund", "r16": "return", "r17": "exchange"}.get(cid)
                ok = interrupt.get("type") == "write_approval" and (
                    wanted_action is None or interrupt.get("action") == wanted_action
                )
            elif expected:
                ok = bool(tools & expected)
            else:
                ok = bool(interrupt)
            rows.append(
                {
                    "id": cid,
                    "message": message,
                    "expected": sorted(expected),
                    "tools": sorted(tools),
                    "write": interrupt.get("type") == "write_approval",
                    "ok": ok,
                }
            )

        passed = sum(1 for row in rows if row["ok"])
        report = {"cases": len(rows), "passed": passed, "rate": round(passed / len(rows), 3), "rows": rows}
        docs = Path(__file__).resolve().parents[2] / "docs" / "eval"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "2026-11-15-react15.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({"cases": len(rows), "passed": passed, "rate": report["rate"]}, ensure_ascii=False))
        for row in rows:
            if not row["ok"]:
                print("FAIL", row)


if __name__ == "__main__":
    asyncio.run(main())
