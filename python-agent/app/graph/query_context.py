"""QueryContext：把用户话里的订单、时间、候选、动作统一解析。

ReAct 仍负责语言和工具选择；这里只提供确定性上下文，避免模型自行改日期/猜单。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.graph.time_refs import parse_time_reference

ORDER_RE = re.compile(r"(CS\d{7,})", re.IGNORECASE)
WRITE_ACTIONS = {"refund", "return", "exchange"}
ALL_ACTIONS = WRITE_ACTIONS | {"urge"}


@dataclass
class QueryContext:
    order_no: str | None = None
    selected_order: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    time_field: str | None = None
    time_from: str | None = None
    time_to: str | None = None
    action: str | None = None

    def apply_find_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """相对时间由系统注入，模型不能把 11-14 改成 11-15。"""
        updated = dict(args)
        if self.time_from and self.time_to:
            updated[f"{self.time_field or 'created'}_from"] = self.time_from
            updated[f"{self.time_field or 'created'}_to"] = self.time_to
        return updated

    def prompt(self) -> str:
        lines: list[str] = []
        if self.candidates:
            lines.append(
                "上一轮候选："
                + "；".join(
                    f"{item.get('orderNo')}（{item.get('status')}，下单 {item.get('createdAt')}，"
                    f"签收 {item.get('deliveredAt') or '无'}）"
                    for item in self.candidates[:5]
                )
            )
            lines.append("用户如果用一个日期/序号回答，直接选对应订单，不要再说查不到。")
        if self.selected_order:
            lines.append(f"用户本轮已选订单：{self.selected_order}。")
        if self.action:
            lines.append(f"本轮识别到的动作：{self.action}。")
        return "\n".join(lines)


def infer_action(text: str) -> str | None:
    """只把「明确请求」当动作；「能退吗」是政策询问，不触发写操作。"""
    request = any(
        word in text
        for word in ("我要", "我想", "帮我", "申请", "给我", "退掉", "退了吧", "不要了", "不想要了", "换", "能换")
    )
    if not request and "退货" in text and "政策" not in text:
        request = True
    if not request:
        return None
    if any(word in text for word in ("退货", "退掉", "退了吧", "退回去")):
        return "return"
    if any(word in text for word in ("换货", "换个", "换一", "换颜色", "换码", "换大", "换小")):
        return "exchange"
    if any(word in text for word in ("催", "催一下", "催催")):
        return "urge"
    if any(word in text for word in ("退款", "退钱")):
        return "refund"
    return None


def resolve_candidate(text: str, candidates: list[dict[str, Any]]) -> str | None:
    explicit = ORDER_RE.search(text)
    if explicit:
        return explicit.group(1).upper()

    ordinals = {"第一个": 0, "第一": 0, "第二个": 1, "第二": 1, "第三个": 2, "第三": 2}
    for word, index in ordinals.items():
        if word in text and index < len(candidates):
            value = str(candidates[index].get("orderNo") or "")
            return value or None

    hint = parse_time_reference(text)
    if not hint or not candidates:
        return None
    key = "createdAt" if hint["field"] == "created" else "deliveredAt"
    matched = [
        str(item.get("orderNo"))
        for item in candidates
        if item.get(key) and hint["from"] <= str(item[key])[:10] <= hint["to"]
    ]
    return matched[0] if len(set(matched)) == 1 else None


def build_context(text: str, state: dict[str, Any]) -> QueryContext:
    candidates = list(state.get("last_candidates") or [])
    selected = resolve_candidate(text, candidates)
    explicit = ORDER_RE.search(text)
    order_no = selected or (explicit.group(1).upper() if explicit else None)
    hint = parse_time_reference(text)
    action = state.get("pending_write_action") or infer_action(text)
    return QueryContext(
        order_no=order_no,
        selected_order=selected,
        candidates=candidates,
        time_field=hint["field"] if hint else None,
        time_from=hint["from"] if hint else None,
        time_to=hint["to"] if hint else None,
        action=action,
    )
