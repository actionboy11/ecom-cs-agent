"""工作台的纯逻辑：便于单测，UI 只负责编排。"""

from __future__ import annotations

ROLE_AGENT = "CS_AGENT"


def can_review(role: str | None) -> bool:
    """与 API 侧同口径：兼容 Spring 的 ROLE_ 前缀，大小写不敏感。"""
    return bool(role) and role.upper().removeprefix("ROLE_") == ROLE_AGENT


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
