"""把 PendingCase + 已选订单转换成统一表单。"""

from __future__ import annotations

from typing import Any

from app.graph.pending import QUALITY_HINTS
from app.tools import business_api


async def build_form(token: str, order_no: str, case: dict[str, Any]) -> dict[str, Any] | None:
    action = str(case.get("action") or "")
    if action not in ("return", "exchange", "invoice", "address"):
        return None
    original = str(case.get("original_text") or "")
    quality = any(word in original for word in QUALITY_HINTS)
    eligibility = await business_api.order_eligibility(order_no, action, token, quality=quality)
    if not eligibility.get("allowed"):
        return None
    next_action = str(eligibility.get("nextAction") or "")
    if action in ("return", "exchange") and next_action not in ("RETURN_FORM", "EXCHANGE_FORM"):
        return None
    fields = {
        "return": ["reason", "evidence"],
        "exchange": ["reason", "evidence", "target"],
        "invoice": ["title", "taxId", "email"],
        "address": ["receiver", "phone", "address"],
    }[action]
    order = await business_api.get_order(order_no, token)
    return {
        "type": "user_action",
        "action": action,
        "order_no": order_no,
        "order_summary": f"{order.get('item')}，{order.get('status')}",
        "message": {
            "return": "请填写退货原因和凭证",
            "exchange": "请填写换货原因、凭证和目标规格",
            "invoice": "请填写发票抬头、税号和邮箱",
            "address": "请填写收件人、手机号和新地址",
        }[action],
        "fields": fields,
        "after_sales_type": {"return": "RETURN", "exchange": "EXCHANGE"}.get(action),
        "shipping_payer": eligibility.get("shippingPayer"),
        "requires_evidence": eligibility.get("requiresEvidence", False),
    }
