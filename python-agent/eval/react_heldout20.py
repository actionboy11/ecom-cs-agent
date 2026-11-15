"""独立 20 条 ReAct held-out：写操作自动确认并核对订单/类型，读操作核对工具。"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import httpx

CASES = [
    ("h01", "我的跑鞋开胶了", {"find_my_orders"}, None),
    ("h02", "上周买的鞋到哪了", {"find_my_orders"}, None),
    ("h03", "上个月买的耳机", {"find_my_orders"}, None),
    ("h04", "登机箱轮子坏了", {"find_my_orders"}, None),
    ("h05", "保温杯漏水", {"find_my_orders"}, None),
    ("h06", "我的背包多少钱", {"find_my_orders", "get_product"}, None),
    ("h07", "CS2024108 到哪了", {"query_logistics"}, None),
    ("h08", "CS2024107 订单详情", {"query_order"}, None),
    ("h09", "拆封的耳机能退吗", {"search_policy"}, None),
    ("h10", "赠品耳机坏了", set(), "handoff"),
    ("h11", "我要退款 CS2024106，质量问题", set(), ("refund", "CS2024106", "REFUND")),
    ("h12", "我要退货 CS2024105，开胶", set(), ("return", "CS2024105", "RETURN")),
    ("h13", "我要换货 CS2024101，换43码", set(), ("exchange", "CS2024101", "EXCHANGE")),
    ("h14", "最近3天买的杯子", {"find_my_orders"}, None),
    ("h15", "上个月买的行李箱", {"find_my_orders"}, None),
    ("h16", "我的杯子想退货", {"find_my_orders"}, None),
    ("h17", "退款要多久到账", {"search_policy"}, None),
    ("h18", "镜子的订单", {"find_my_orders"}, "fallback"),
    ("h19", "耳机多少钱", {"find_my_orders", "get_product"}, None),
    ("h20", "CS2024102 物流", {"query_logistics"}, None),
]


async def main() -> None:
    await asyncio.to_thread(
        subprocess.run,
        ["docker", "compose", "exec", "-T", "mysql", "mysql", "-ucsagent", "-pcsagent",
         "cs_agent", "-e", "DELETE FROM after_sales_requests;"],
        cwd=str(Path(__file__).resolve().parents[2]), capture_output=True, check=False,
    )
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        token = (
            await client.post(
                "http://localhost:8080/api/auth/login",
                json={"username": "buyer_test", "password": "demo123"},
            )
        ).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        rows = []
        for cid, message, tools, write in CASES:
            thread = f"heldout-react-{cid}"
            resp = await client.post(
                "http://localhost:8000/api/v1/chat",
                json={"thread_id": thread, "message": message},
                headers=headers,
            )
            data = resp.json()
            seen = {item.get("tool") for item in (data.get("tool_trace") or []) if item.get("tool")}
            interrupt = data.get("interrupt") or {}
            fallback = data.get("fallback_reason")
            ok = False
            detail = ""

            if isinstance(write, tuple):
                action, order_no, as_type = write
                if interrupt.get("type") == "write_approval" and interrupt.get("action") == action:
                    confirm = await client.post(
                        f"http://localhost:8000/api/v1/threads/{thread}/confirm",
                        json={"approved": True},
                        headers=headers,
                    )
                    after = (
                        await client.get("http://localhost:8080/api/after-sales", headers=headers)
                    ).json()
                    matched = [
                        row for row in after
                        if row["orderNo"] == order_no and row["type"] == as_type
                    ]
                    ok = confirm.status_code == 200 and bool(matched)
                    detail = f"created={bool(matched)}"
                else:
                    detail = f"interrupt={interrupt.get('action')}"
            elif write == "handoff":
                ok = bool(interrupt)
            elif write == "fallback":
                ok = fallback == "no_candidates"
            else:
                ok = bool(seen & tools)

            rows.append(
                {"id": cid, "message": message, "expected": sorted(tools), "seen": sorted(seen),
                 "fallback": fallback, "ok": ok, "detail": detail}
            )

        passed = sum(1 for row in rows if row["ok"])
        wrong_order = sum(
            1 for row in rows if row["detail"].startswith("created=False")
        )
        report = {
            "cases": len(rows),
            "passed": passed,
            "rate": round(passed / len(rows), 3),
            "wrong_order": wrong_order,
            "rows": rows,
        }
        docs = Path(__file__).resolve().parents[2] / "docs" / "eval"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "2026-11-15-react-heldout20.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({"cases": len(rows), "passed": passed, "rate": report["rate"],
                          "wrong_order": wrong_order}, ensure_ascii=False))
        for row in rows:
            if not row["ok"]:
                print("FAIL", row)


if __name__ == "__main__":
    asyncio.run(main())
