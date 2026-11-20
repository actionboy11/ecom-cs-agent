"""多轮待办：候选订单 + 用户动作 + 原话。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

ACTION_WORDS = {
    "invoice": ("发票", "开票"),
    "address": ("地址", "收件人", "收货信息"),
    "exchange": ("换", "换货", "换一个"),
}
QUALITY_HINTS = ("坏", "破", "漏", "质量", "故障", "开线", "杂音", "磕", "充不进", "不工作", "异响", "差", "晃", "拧不上", "发错", "不对", "松动", "卡")


def infer_action(text: str, intent: str | None) -> str | None:
    for action, words in ACTION_WORDS.items():
        if any(word in text for word in words):
            return action
    if "退" in text:
        return "return"
    if intent in ("refund", "return", "exchange"):
        return str(intent)
    return None


def remember(action: str | None, original_text: str, candidates: list[dict[str, Any]], target: str | None = None) -> dict[str, Any]:
    return {
        "action": action,
        "original_text": original_text,
        "candidates": candidates[:5],
        "target": target,
        "selected_order": None,
        "created_at": datetime.now(UTC).isoformat(),
    }


def candidate_orders(case: dict[str, Any] | None) -> set[str]:
    if not case:
        return set()
    return {str(row.get("orderNo")) for row in case.get("candidates") or [] if row.get("orderNo")}
