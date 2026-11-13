"""工作台的纯逻辑：便于单测，UI 只负责编排。"""

from __future__ import annotations

ROLE_AGENT = "CS_AGENT"
ROLE_CUSTOMER = "CUSTOMER"


def can_review(role: str | None) -> bool:
    """与 API 侧同口径：兼容 Spring 的 ROLE_ 前缀，大小写不敏感。"""
    return bool(role) and role.upper().removeprefix("ROLE_") == ROLE_AGENT


def is_customer(role: str | None) -> bool:
    """买家专属面板（售后进度）只对 CUSTOMER 展示，避免坐席看到「我的」全部数据。"""
    return bool(role) and role.upper().removeprefix("ROLE_") == ROLE_CUSTOMER


_HANDOFF_REASONS = {"complaint": "投诉", "turn_limit": "轮次上限"}


def handoff_label(reason: str | None) -> str:
    """待办原因：未知原因不要硬说成「投诉」。"""
    if not reason:
        return "人工转接"
    return _HANDOFF_REASONS.get(reason, str(reason))


def format_reply(reply: dict) -> str:
    """把 Agent 响应拼成展示文本：正文 + 人工转接提示（买家只能等待）。"""
    content = str(reply.get("reply") or "")
    if reply.get("needs_human"):
        content += "\n\n_（已转接人工坐席，请等待处理）_"
    return content


def audit_row(row: dict) -> dict:
    """审计行 → 表格行；Java 的时间字段是 `ts`。"""
    return {
        "时间": row.get("ts", ""),
        "操作者": row.get("actor", ""),
        "动作": row.get("action", ""),
        "资源": row.get("resourceId", ""),
        "结果": row.get("result", ""),
    }
