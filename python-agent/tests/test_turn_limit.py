"""S6/P0-2：单会话 10 轮上限（SPEC §8）。"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.config import settings
from app.graph.builder import build_graph
from app.graph.nodes import MAX_TURNS
from app.knowledge import store as knowledge_store


def _offline(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "qwen_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "deepseek_api_key", "test")
    monkeypatch.setattr(settings, "qwen_api_key", "test")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.5)


async def _send(graph, config, text: str) -> dict:
    return await graph.ainvoke(
        {"messages": [HumanMessage(content=text)], "thread_id": config["configurable"]["thread_id"]},
        config,
    )


@pytest.mark.asyncio
async def test_eleventh_turn_goes_to_human_without_tools(monkeypatch) -> None:
    _offline(monkeypatch)
    knowledge_store.configure(None)
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "t-turn-limit"}}

    for _ in range(MAX_TURNS):
        result = await _send(graph, config, "退货政策几天")
        assert not result.get("turn_limit")

    assert result["turn_count"] == MAX_TURNS

    over = await _send(graph, config, "退货政策几天")

    assert over["turn_limit"] is True
    assert over["turn_count"] == MAX_TURNS + 1
    assert over["needs_human"] is True
    assert "上限" in over["reply"]
    # 超过上限后不再调用工具
    assert not over.get("tool_result")


@pytest.mark.asyncio
async def test_turn_limit_is_per_thread(monkeypatch) -> None:
    _offline(monkeypatch)
    knowledge_store.configure(None)
    graph = build_graph(MemorySaver())

    for i in range(MAX_TURNS):
        await _send(graph, {"configurable": {"thread_id": f"t-limit-a-{i}"}}, "退货政策几天")

    fresh = await _send(graph, {"configurable": {"thread_id": "t-limit-b"}}, "退货政策几天")
    assert fresh["turn_count"] == 1
    assert not fresh.get("turn_limit")
