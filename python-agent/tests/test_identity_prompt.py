"""身份核验提示：登录态已确认身份，不得再让用户报手机号。"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graph import nodes
from app.knowledge.store import RetrievalResult


@pytest.mark.asyncio
async def test_respond_prompt_forbids_identity_recheck(monkeypatch) -> None:
    captured: dict = {}

    async def fake_invoke(messages, **_kwargs):
        captured["messages"] = messages
        return AIMessage(content="订单已签收")

    monkeypatch.setattr(nodes, "ainvoke_with_fallback", fake_invoke)
    monkeypatch.setattr(
        nodes.knowledge_store, "retrieve", lambda *_a, **_k: RetrievalResult(None, [], "none")
    )

    state = {
        "thread_id": "t-identity",
        "messages": [HumanMessage(content="帮我查一下订单 CS2024001")],
        "intent": "order_query",
        "tool_result": {"tool": "query_order", "data": {"status": "已签收"}},
        "policy_refs": [],
    }
    await nodes.respond_node(state)

    system = next(m for m in captured["messages"] if isinstance(m, SystemMessage))
    assert "身份已由系统登录态验证" in system.content
    assert "手机号" in system.content


@pytest.mark.asyncio
async def test_order_intent_does_not_cite_identity_policies(monkeypatch) -> None:
    async def fake_invoke(_messages, **_kwargs):
        return AIMessage(content="订单已签收")

    monkeypatch.setattr(nodes, "ainvoke_with_fallback", fake_invoke)
    monkeypatch.setattr(
        nodes.knowledge_store,
        "retrieve",
        lambda *_a, **_k: RetrievalResult(None, ["P01", "P10", "P12"], "keyword"),
    )

    result = await nodes.respond_node(
        {
            "thread_id": "t-identity-2",
            "messages": [HumanMessage(content="查订单")],
            "intent": "order_query",
            "tool_result": {"tool": "query_order", "data": {"status": "已签收"}},
            "policy_refs": [],
        }
    )

    assert result["policy_refs"] == ["P01"]
