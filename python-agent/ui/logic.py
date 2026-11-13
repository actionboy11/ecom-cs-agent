"""工作台的纯逻辑：便于单测，UI 只负责编排。"""

from __future__ import annotations

ROLE_AGENT = "CS_AGENT"


def can_review(role: str | None) -> bool:
    return role == ROLE_AGENT


def format_reply(reply: dict) -> str:
    """把 Agent 响应拼成展示文本：正文 + 转人工提示。"""
    content = str(reply.get("reply") or "")
    if reply.get("needs_human"):
        content += "\n\n_（已转人工，坐席可在右侧处理）_"
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
