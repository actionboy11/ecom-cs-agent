"""30 条订单匹配评测：直接调 find_my_orders，按「自动选中/追问」判定。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from app.tools.business_api import find_my_orders

CASES = [
    ("m01", ["鞋"], None, None, None, None, "refund", "ask"),
    ("m02", ["鞋"], "2026-10-01", "2026-10-31", None, None, "refund", "CS2024105"),
    ("m03", ["鞋"], None, None, "2026-11-01", "2026-11-30", "refund", "CS2024101"),
    ("m04", ["鞋"], "2026-11-01", "2026-11-30", None, None, "query", "ask"),
    ("m05", ["耳机"], None, None, None, None, "refund", "ask"),
    ("m06", ["耳机"], None, None, "2026-10-01", "2026-10-31", "refund", "CS2024106"),
    ("m07", ["耳机"], "2026-11-01", "2026-11-30", None, None, "logistics", "ask"),
    ("m08", ["耳机"], "2026-11-01", "2026-11-13", None, None, "logistics", "CS2024102"),
    ("m09", ["行李箱"], None, None, None, None, "refund", "ask"),
    ("m10", ["行李箱"], None, None, "2026-10-01", "2026-10-31", "refund", "CS2024107"),
    ("m11", ["行李箱"], "2026-11-01", "2026-11-30", None, None, "logistics", "CS2024103"),
    ("m12", ["杯子"], None, None, None, None, "refund", "ask"),
    ("m13", ["杯子"], "2026-11-01", "2026-11-30", None, None, "refund", "CS2024104"),
    ("m14", ["杯子"], None, None, "2026-10-01", "2026-10-31", "refund", "CS2024108"),
    ("m15", ["背包"], None, None, None, None, "refund", "CS2024109"),
    ("m16", ["充电宝"], "2026-11-01", "2026-11-30", None, None, "logistics", "CS2024110"),
    ("m17", ["镜子"], None, None, None, None, "refund", "none"),
    ("m18", ["耳机"], None, None, "2026-10-17", "2026-10-17", "query", "CS2024106"),
    ("m19", ["鞋"], None, None, "2026-11-12", "2026-11-12", "exchange", "CS2024101"),
    ("m20", ["鞋"], "2026-11-10", "2026-11-10", None, None, "return", "CS2024101"),
    ("m21", ["行李箱"], "2026-11-01", "2026-11-01", None, None, "query", "CS2024103"),
    ("m22", ["杯子"], "2026-11-14", "2026-11-14", None, None, "query", "CS2024104"),
    ("m23", ["背包"], None, None, "2026-11-10", "2026-11-10", "query", "CS2024109"),
    ("m24", ["充电宝"], "2026-11-03", "2026-11-03", None, None, "query", "CS2024110"),
    ("m25", ["耳机"], None, None, "2026-10-17", "2026-10-17", "refund", "CS2024106"),
    ("m26", ["鞋"], "2026-10-20", "2026-10-20", None, None, "refund", "CS2024105"),
    ("m27", ["行李箱"], "2026-11-05", "2026-11-05", None, None, "refund", "none"),
    ("m28", ["杯子"], "2026-10-25", "2026-10-25", None, None, "refund", "CS2024108"),
    ("m29", ["耳机"], None, None, "2026-10-17", "2026-10-17", "query", "CS2024106"),
    ("m30", ["鞋"], "2026-11-10", "2026-11-10", None, None, "logistics", "CS2024101"),
]


async def main() -> None:
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        token = (
            await client.post(
                "http://localhost:8080/api/auth/login",
                json={"username": "buyer_test", "password": "demo123"},
            )
        ).json()["token"]

        rows = []
        for cid, terms, cf, ct, df, dt, action, expected in CASES:
            candidates = await find_my_orders(
                token,
                product_terms=terms,
                created_from=cf,
                created_to=ct,
                delivered_from=df,
                delivered_to=dt,
                action=action,
            )
            top = candidates[0] if candidates else None
            second = candidates[1] if len(candidates) > 1 else None
            auto = bool(
                top
                and top["score"] >= 0.8
                and (second is None or top["score"] - second["score"] >= 0.15)
            )
            actual = top["orderNo"] if auto else ("none" if not candidates else "ask")
            ok = actual == expected
            rows.append({"id": cid, "expected": expected, "actual": actual, "ok": ok,
                         "top": top["orderNo"] if top else None,
                         "top_score": top["score"] if top else None})

        passed = sum(1 for row in rows if row["ok"])
        report = {"cases": len(rows), "passed": passed, "rate": round(passed / len(rows), 3), "rows": rows}
        docs = Path(__file__).resolve().parents[2] / "docs" / "eval"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "2026-11-15-matching30.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({"cases": len(rows), "passed": passed, "rate": report["rate"]}, ensure_ascii=False))
        for row in rows:
            if not row["ok"]:
                print("FAIL", row)


if __name__ == "__main__":
    asyncio.run(main())
