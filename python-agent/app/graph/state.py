"""Agent 状态定义：LangGraph 的共享「白板」。"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # 会话标识（checkpointer 用它区分会话；由 API 层写入）
    thread_id: str
    user_id: str | None

    # 会话消息（add_messages 负责追加与去重）
    messages: Annotated[list[BaseMessage], add_messages]

    # 意图与槽位
    intent: str
    order_no: str | None
    reason: str | None
    confidence: float

    # 中间结果
    tool_result: dict[str, Any] | None
    knowledge: str | None

    # 人工介入
    needs_human: bool
    handoff_reason: str | None
    handoff_summary: str | None
    handoff_approved: bool | None

    # 最终回复
    reply: str


INTENTS = (
    "order_query",
    "logistics",
    "refund",
    "policy",
    "complaint",
    "other",
)
