"""图装配：这里是「Agent 长什么样」的唯一事实来源。"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph import nodes
from app.graph.state import AgentState


def build_graph(checkpointer: Any):
    """编译状态机。

    checkpointer 必须显式传入：生产用 SQLite（`app.graph.checkpointer`），
    批处理/单测可用 `MemorySaver`。刻意不设默认值——避免生产误用内存实现。
    """
    graph = StateGraph(AgentState)

    graph.add_node("classify", nodes.classify)
    graph.add_node("tools", nodes.tool_node)
    graph.add_node("handoff_prepare", nodes.handoff_prepare)
    graph.add_node("await_human", nodes.await_human)
    graph.add_node("respond", nodes.respond_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        nodes.route_after_classify,
        {
            "tools": "tools",
            "handoff": "handoff_prepare",
            "respond": "respond",
        },
    )
    graph.add_edge("tools", "respond")
    # 转人工两段式：先写答复（可落盘）→ 再 interrupt 挂起 → 人工恢复后继续
    graph.add_edge("handoff_prepare", "await_human")
    graph.add_edge("await_human", "respond")
    graph.add_edge("respond", END)

    return graph.compile(checkpointer=checkpointer)


_graph: Any = None


def set_graph(graph: Any) -> None:
    """由 FastAPI lifespan 注入带 SQLite checkpointer 的图。"""
    global _graph
    _graph = graph


def get_graph():
    """取当前图。未初始化时直接报错，而不是悄悄退回内存实现。"""
    if _graph is None:
        raise RuntimeError("Agent 图未初始化：应通过 lifespan 打开 SQLite checkpointer")
    return _graph


def reset_graph() -> None:
    """测试用：清空单例。"""
    global _graph
    _graph = None
