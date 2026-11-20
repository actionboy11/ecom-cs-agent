"""ReAct 前的确定性预取：订单、物流、售后、运输中拦截。

模型不再负责“是否记得查订单/查物流/拦截”；这些事实由代码先取好。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.tools import business_api

ORDER_RE = re.compile(r"(CS\d{7,})", re.IGNORECASE)
AFTER_SALES_HINTS = ("换货申请", "退款申请", "审核", "进度", "补发", "到账", "退款被拒", "退货申请", "少了", "少退", "扣我", "差额")
LOGISTICS_HINTS = ("物流", "到哪", "没收到", "运输", "快递", "签收", "发货", "补发")
URGE_HINTS = ("催", "不发货", "必须发", "差评")
ORDER_INTENTS = {"order_query", "logistics", "refund", "return", "exchange", "urge"}


@dataclass
class Preflight:
    order_no: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    ambiguous: bool = False
    intercept_failed: bool = False
    refund_unresolved: bool = False


async def run_preflight(
    text: str, state: dict[str, Any], token: str, explicit_order: str | None = None
) -> Preflight:
    intent = str(state.get("intent") or "other")
    order_no = explicit_order or (ORDER_RE.search(text).group(1).upper() if ORDER_RE.search(text) else None)
    result = Preflight(order_no=order_no)

    if not order_no and intent in ORDER_INTENTS:
        product_terms = state.get("matched_products") or []
        if product_terms or intent in ("order_query", "logistics", "refund", "return", "exchange"):
            try:
                found = await business_api.find_my_orders(
                    token, product_terms=product_terms or None, limit=5
                )
            except Exception:  # noqa: BLE001
                found = []
            if found:
                result.trace.append({"step": -1, "tool": "find_my_orders", "args": {}, "result": str(found)})
                result.candidates = found
                if len(found) == 1:
                    order_no = result.order_no = str(found[0].get("orderNo"))
                else:
                    result.ambiguous = True
                    result.facts.append(f"候选订单：{[row.get('orderNo') for row in found[:5]]}")
            if not order_no:
                return result

    if not order_no:
        return result

    try:
        order = await business_api.get_order(order_no, token)
        result.trace.append({"step": -1, "tool": "query_order", "args": {"order_no": order_no}, "result": str(order)})
        result.facts.append(
            f"订单 {order_no}：{order.get('item')}，状态 {order.get('status')}，签收 {order.get('deliveredAt')}"
        )
    except Exception:  # noqa: BLE001
        return result

    refund_issue = state.get("pending_issue") == "refund_discrepancy" or any(
        word in text for word in ("少了", "少退", "扣我", "差额")
    )
    if any(word in text for word in AFTER_SALES_HINTS) or refund_issue:
        try:
            rows = await business_api.list_after_sales(token)
            rows = [row for row in rows if row.get("orderNo") == order_no]
            if refund_issue:
                # 当前没有退款金额/扣费明细，查到记录也要人工核实
                result.refund_unresolved = True
            rows = [row for row in rows if row.get("orderNo") == order_no]
            result.trace.append({"step": -1, "tool": "query_after_sales", "args": {"order_no": order_no}, "result": str(rows)})
            result.facts.append(f"售后记录：{rows}")
        except Exception:  # noqa: BLE001
            result.facts.append("售后查询失败")

    if any(word in text for word in LOGISTICS_HINTS) or intent == "logistics":
        try:
            logistics = await business_api.get_logistics(order_no, token)
            result.trace.append({"step": -1, "tool": "query_logistics", "args": {"order_no": order_no}, "result": str(logistics)})
            result.facts.append(f"物流：{logistics}")
        except Exception:  # noqa: BLE001
            result.facts.append("物流查询失败")

    if any(word in text for word in URGE_HINTS) or intent == "urge":
        try:
            urged = await business_api.urge_logistics(order_no, token)
            result.trace.append({"step": -1, "tool": "urge_logistics", "args": {"order_no": order_no}, "result": str(urged)})
            result.facts.append(f"催件：{urged}")
        except Exception:  # noqa: BLE001
            result.facts.append("催件失败")

    status = str(order.get("status") or "")
    if intent == "refund" and status in ("已发货", "运输中"):
        try:
            intercepted = await business_api.intercept_logistics(order_no, token)
            result.trace.append({"step": -1, "tool": "intercept_order", "args": {"order_no": order_no}, "result": str(intercepted)})
            result.facts.append(f"拦截：{intercepted}")
            if intercepted.get("status") == "FAILED":
                result.intercept_failed = True
        except Exception:  # noqa: BLE001
            result.intercept_failed = True
    return result
