"""P0-2：单会话 10 轮上限（SPEC §8），超过后真实转人工挂起。"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.graph.builder import build_graph
from app.graph.nodes import MAX_TURNS, route_after_classify


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


async def _seed(graph, thread_id: str, turn_count: int, **extra) -> None:
    await graph.aupdate_state(_config(thread_id), {"turn_count": turn_count, **extra})


@pytest.mark.asyncio
async def test_turn_11_hands_off_without_model_or_tools(monkeypatch, offline_llm) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("超过轮次上限后不应再调用模型")

    monkeypatch.setattr("app.graph.nodes.with_structured_output", boom)

    graph = build_graph(MemorySaver())
    await _seed(graph, "t-limit", MAX_TURNS)

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="CS2024001 到哪了")], "thread_id": "t-limit"},
        _config("t-limit"),
    )

    assert result["turn_count"] == MAX_TURNS + 1
    assert result["needs_human"] is True
    assert result["handoff_reason"] == "turn_limit"
    assert "上限" in result["reply"]
    assert result.get("tool_result") is None
    # 真实挂起：有 interrupt，坐席可以恢复
    assert result.get("__interrupt__")


@pytest.mark.asyncio
async def test_turn_10_is_still_normal(monkeypatch, offline_llm) -> None:
    graph = build_graph(MemorySaver())
    await _seed(graph, "t-ten", MAX_TURNS - 1)

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="退货政策几天")], "thread_id": "t-ten"},
        _config("t-ten"),
    )

    assert result["turn_count"] == MAX_TURNS
    assert not result.get("needs_human", False)


def test_route_prefers_refusal_then_limit() -> None:
    assert route_after_classify({"refusal": "标准话术", "turn_count": 99}) == "refuse"
    assert route_after_classify({"refusal": None, "turn_count": 11, "intent": "other"}) == "handoff"
    assert route_after_classify({"refusal": None, "turn_count": 10, "intent": "logistics"}) == "tools"


@pytest.mark.asyncio
async def test_turn_count_is_per_thread(offline_llm) -> None:
    graph = build_graph(MemorySaver())
    await _seed(graph, "t-a", MAX_TURNS)
    await _seed(graph, "t-b", 0)

    over = await graph.ainvoke(
        {"messages": [HumanMessage(content="你好")], "thread_id": "t-a"}, _config("t-a")
    )
    fresh = await graph.ainvoke(
        {"messages": [HumanMessage(content="你好")], "thread_id": "t-b"}, _config("t-b")
    )

    assert over["needs_human"] is True
    assert fresh["turn_count"] == 1
    assert not fresh.get("needs_human", False)


@pytest.mark.asyncio
async def test_stale_tool_result_is_cleared_each_turn(offline_llm) -> None:
    graph = build_graph(MemorySaver())
    await _seed(
        graph,
        "t-stale",
        2,
        tool_result={"tool": "logistics", "data": {"status": "运输中"}},
    )

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="退货政策几天")], "thread_id": "t-stale"},
        _config("t-stale"),
    )

    assert result.get("tool_result") is None


@pytest.mark.asyncio
async def test_agent_can_resume_turn_limit_handoff(offline_llm) -> None:
    graph = build_graph(MemorySaver())
    await _seed(graph, "t-limit-resume", MAX_TURNS)
    await graph.ainvoke(
        {"messages": [HumanMessage(content="你好")], "thread_id": "t-limit-resume"},
        _config("t-limit-resume"),
    )

    from langgraph.types import Command

    resumed = await graph.ainvoke(
        Command(resume={"approved": True, "note": "转人工已接入"}),
        _config("t-limit-resume"),
    )
    # 恢复后不再挂起；needs_human 由 API 层按 interrupt 是否存在计算
    assert not resumed.get("__interrupt__")
    assert resumed.get("reply")
