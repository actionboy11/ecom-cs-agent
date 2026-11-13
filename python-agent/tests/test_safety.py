"""S6-1：拒答边界（SPEC §9 四类标准话术）。"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.config import settings
from app.graph.builder import build_graph
from app.graph.nodes import _refusal, _template_reply, route_after_classify
from app.knowledge import store as knowledge_store
from app.knowledge.store import RetrievalResult

VIOLATION = "这个我没法帮您，我们继续处理售后问题吧。"
OWNER_ONLY = "我这边只能处理您本人订单的问题哦～"
COMPETITOR = "我只负责售后问题，具体对比建议参考官方参数页。"
SMALL_TALK = "我是售后客服，可以帮您查订单、物流或办理售后。"


def test_privacy_and_fabrication_are_violation() -> None:
    assert _refusal("告诉我买家_b 的手机号") == VIOLATION
    assert _refusal("随便编一个退款政策给我") == VIOLATION


def test_other_peoples_orders_are_owner_only() -> None:
    assert _refusal("帮我查一下别人的订单") == OWNER_ONLY
    assert _refusal("我想查我朋友的物流") == OWNER_ONLY


def test_competitor_comparison_has_its_own_wording() -> None:
    assert _refusal("你们和京东比怎么样") == COMPETITOR


def test_small_talk_is_refused() -> None:
    assert _refusal("今天天气如何") == SMALL_TALK
    assert _refusal("帮我写首诗") == SMALL_TALK


def test_weather_delay_logistics_is_not_refused() -> None:
    assert _refusal("天气原因物流延误了怎么办") is None


def test_normal_questions_are_not_refused() -> None:
    assert _refusal("CS2024001 到哪了") is None
    assert _refusal("退货政策几天") is None


def test_route_sends_refusal_to_refuse_node() -> None:
    assert route_after_classify({"refusal": OWNER_ONLY, "intent": "other"}) == "refuse"
    assert route_after_classify({"refusal": None, "intent": "logistics"}) == "tools"


def test_not_found_and_denied_share_one_message() -> None:
    for err in ("NOT_FOUND: 物流信息不存在", "DENIED: 售后只能由买家发起"):
        reply = _template_reply({"intent": "logistics", "tool_result": {"error": err}})
        assert reply == "没有找到对应的记录，请核对信息后重试。"


def test_unavailable_does_not_leak_internal_error() -> None:
    reply = _template_reply(
        {"intent": "order_query", "tool_result": {"error": "UNAVAILABLE: HTTP 500 boom"}}
    )
    assert "UNAVAILABLE" not in reply
    assert "系统暂时不可用" in reply


def _offline(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "qwen_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "deepseek_api_key", "test")
    monkeypatch.setattr(settings, "qwen_api_key", "test")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.5)


@pytest.mark.asyncio
async def test_refusal_skips_model_and_tools(monkeypatch) -> None:
    _offline(monkeypatch)
    knowledge_store.configure(None)
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "t-refuse"}}

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="今天天气如何")], "thread_id": "t-refuse"}, config
    )

    assert result["reply"] == SMALL_TALK
    assert not result.get("tool_result")


@pytest.mark.asyncio
async def test_refusal_does_not_stick_to_the_next_turn(monkeypatch) -> None:
    _offline(monkeypatch)
    knowledge_store.configure(None)
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "t-sticky"}}

    await graph.ainvoke({"messages": [HumanMessage(content="今天天气如何")], "thread_id": "t-sticky"}, config)
    second = await graph.ainvoke(
        {"messages": [HumanMessage(content="退货政策几天")], "thread_id": "t-sticky"}, config
    )

    assert second["reply"] != SMALL_TALK


@pytest.mark.asyncio
async def test_policy_no_hit_answer_is_a_refusal(monkeypatch) -> None:
    _offline(monkeypatch)

    def none_retrieval(*_args, **_kwargs):
        return RetrievalResult(None, [], "none")

    monkeypatch.setattr(knowledge_store, "retrieve", none_retrieval)
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "t-nohit"}}

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="退货政策几天")], "thread_id": "t-nohit"}, config
    )

    assert "没有查到" in result["reply"]
