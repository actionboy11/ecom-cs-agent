"""订单定位 skill：无订单号时，先召回候选，再决定自动采用/让用户选/无候选。"""

from __future__ import annotations

from typing import Any

from app.tools import business_api

AUTO_SCORE = 0.8
AUTO_MARGIN = 0.15


async def order_lookup(
    token: str,
    product_terms: list[str] | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    delivered_from: str | None = None,
    delivered_to: str | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    candidates = await business_api.find_my_orders(
        token,
        product_terms=product_terms or [],
        created_from=created_from,
        created_to=created_to,
        delivered_from=delivered_from,
        delivered_to=delivered_to,
        action=action,
        limit=5,
    )
    if not candidates:
        return {"status": "none", "message": "没有匹配订单；列最近订单或转人工", "candidates": []}

    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    margin = top["score"] - (second["score"] if second else 0)
    if top["score"] >= AUTO_SCORE and margin >= AUTO_MARGIN:
        return {"status": "auto", "order_no": top["orderNo"], "order": top, "candidates": candidates[:3]}

    return {
        "status": "ask",
        "message": "有多个候选，让用户选",
        "candidates": candidates[:3],
    }
