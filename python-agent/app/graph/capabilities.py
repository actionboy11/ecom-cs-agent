"""能力注册表：把「不支持但可由用户完成」和「历史账单」从 ReAct 中拿出来。"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date

from app import clock

ORDER_RE = re.compile(r"(CS\d{7,})", re.IGNORECASE)
ADDRESS_WORDS = ("改地址", "换地址", "修改地址", "改收货地址", "改收件人", "换收件人")
INVOICE_WORDS = ("发票", "开票", "开发票")
HISTORY_WORDS = (
    "历史订单", "订单记录", "历史账单", "全部订单", "订单列表",
    "买过什么", "买了什么", "买过哪些", "都买了什么", "消费记录",
)
COMPENSATION_WORDS = (
    "赔偿", "赔钱", "赔我", "能赔", "索赔", "损失",
    "弄湿", "泡了", "泡坏", "电脑坏了", "赔吗",
)


@dataclass
class CapabilityResult:
    kind: str
    payload: dict = field(default_factory=dict)
    reply: str = ""


def _month_range(text: str) -> tuple[str | None, str | None]:
    today = clock.today()
    months = sorted({int(value) for value in re.findall(r"(\d{1,2})\s*月", text)})
    if not months:
        recent = re.search(r"最近\s*(\d+)\s*个月", text)
        if recent:
            count = max(1, min(12, int(recent.group(1))))
            month = today.month - count + 1
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            start = date(year, month, 1)
            return start.isoformat(), today.isoformat()
        return None, None
    first = date(today.year, months[0], 1)
    last_month = months[-1]
    last_day = calendar.monthrange(today.year, last_month)[1]
    end = date(today.year, last_month, last_day)
    if last_month == today.month:
        end = today
    return first.isoformat(), end.isoformat()


def detect(text: str) -> CapabilityResult | None:
    if any(word in text for word in COMPENSATION_WORDS):
        return CapabilityResult(
            kind="handoff_request",
            payload={"reason": "compensation_or_damage", "summary": text},
            reply="这类赔偿/物品损失需要人工核实，我先为您转接。",
        )

    order = ORDER_RE.search(text)
    order_no = order.group(1).upper() if order else None

    address_change = (
        any(word in text for word in ("地址", "收件人"))
        and any(word in text for word in ("改", "换", "修改"))
    )
    if any(word in text for word in ADDRESS_WORDS) or address_change:
        return CapabilityResult(
            kind="user_action_request",
            payload={"action": "change_address", "order_no": order_no},
        )

    if any(word in text for word in INVOICE_WORDS):
        return CapabilityResult(
            kind="user_action_request",
            payload={"action": "invoice", "order_no": order_no},
        )

    if any(word in text for word in HISTORY_WORDS):
        start, end = _month_range(text)
        payload = {
            "type": "order_history",
            "page": 1,
            "page_size": 10,
            "created_from": start,
            "created_to": end,
            "total": None,
            "has_more": None,
        }
        return CapabilityResult(
            kind="order_history",
            payload=payload,
            reply="已为你打开订单记录，每页 10 条，可以点下一页继续查看。",
        )

    return None
