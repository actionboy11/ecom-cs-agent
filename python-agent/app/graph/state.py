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
    sku: str | None
    reason: str | None
    confidence: float

    # 中间结果
    tool_result: dict[str, Any] | None
    knowledge: str | None
    policy_refs: list[str]

    # 人工介入
    needs_human: bool
    handoff_reason: str | None
    handoff_summary: str | None
    handoff_approved: bool | None

    # 安全拒答：命中后走 refuse → respond（SPEC §8）
    refusal: str | None
    safety_reply: str | None

    # 轮次上限：turn_count > 10 时走转人工兜底（SPEC §8）
    turn_count: int
    turn_limit: bool

    # 最终回复
    reply: str


INTENTS = (
    "order_query",
    "logistics",
    "refund",
    "policy",
    "complaint",
    "product_info",
    "other",
)
