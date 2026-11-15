"""退货 skill：正常退货 / 定制退货。

Skill 只做「判定 + 给出下一步」，真正写操作仍由 ReAct 调 create_return/create_refund，
并经过人工确认。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.tools import business_api

QUALITY_HINTS = ("质量问题", "坏了", "开线", "漏水", "杂音", "破损", "发错", "错色", "故障")


def _tags(order: dict[str, Any]) -> set[str]:
    raw = order.get("tags") or ""
    return {item.strip() for item in str(raw).split(",") if item.strip()}


def _delivered_date(order: dict[str, Any]) -> date | None:
    value = order.get("deliveredAt")
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _quality(reason: str) -> bool:
    return any(word in reason for word in QUALITY_HINTS)


async def normal_return(
    token: str, order_no: str, reason: str, today: date | None = None
) -> dict[str, Any]:
    order = await business_api.get_order(order_no, token)
    tags = _tags(order)
    if "custom" in tags:
        return {
            "status": "wrong_skill",
            "message": "这是定制商品，必须改用 custom_return_skill",
            "order_no": order_no,
        }
    if order.get("status") != "已签收":
        return {
            "status": "not_signed",
            "message": "未签收，不能按已签收退货处理；先说明需签收后申请或拒收",
            "order_no": order_no,
        }
    delivered = _delivered_date(order)
    if delivered is None:
        return {"status": "missing_delivered", "message": "缺少签收时间，转人工", "order_no": order_no}
    days = ((today or date.today()) - delivered).days
    if days > 7:
        return {
            "status": "out_of_window",
            "message": "超过七天无理由；质量问题仍在 15 天内可走 P02，否则转人工",
            "order_no": order_no,
            "days": days,
        }
    if _quality(reason):
        return {
            "status": "ready",
            "action": "confirm_create",
            "as_type": "RETURN",
            "policy": "P02",
            "order_no": order_no,
            "message": "质量问题退货，走 P02，确认后创建 RETURN",
        }
    return {
        "status": "ready",
        "action": "confirm_create",
        "as_type": "RETURN",
        "policy": "P01",
        "order_no": order_no,
        "message": "七天无理由退货，确认后创建 RETURN",
    }


async def custom_return(
    token: str, order_no: str, reason: str, today: date | None = None
) -> dict[str, Any]:
    order = await business_api.get_order(order_no, token)
    tags = _tags(order)
    if "custom" not in tags:
        return {
            "status": "wrong_skill",
            "message": "不是定制商品，改用 normal_return_skill",
            "order_no": order_no,
        }
    delivered = _delivered_date(order)
    days = ((today or date.today()) - delivered).days if delivered else None

    if _quality(reason):
        if days is not None and days <= 15:
            return {
                "status": "ready",
                "action": "confirm_create",
                "as_type": "RETURN",
                "policy": "P02",
                "order_no": order_no,
                "message": "定制商品有质量问题，15 天内走 P02，确认后创建 RETURN",
            }
        return {
            "status": "handoff",
            "message": "定制商品有质量问题但已超 15 天，转人工",
            "order_no": order_no,
        }

    return {
        "status": "handoff",
        "message": "定制商品不适用七天无理由，且无质量问题；解释政策并转人工",
        "order_no": order_no,
    }
