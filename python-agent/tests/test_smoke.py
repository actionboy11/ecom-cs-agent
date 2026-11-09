"""冒烟测试：不依赖任何 API Key 也能跑。

原则：脚手架必须先「无外部依赖可跑通」，否则 D1 会被环境问题拖死。
"""

import asyncio

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.graph.builder import build_graph
from app.graph.nodes import _keyword_classify, handoff_prepare, route_after_classify


def test_graph_builds() -> None:
    graph = build_graph(MemorySaver())
    assert graph is not None


def test_keyword_classify_intents() -> None:
    assert _keyword_classify("帮我查订单 CS2024001").intent == "order_query"
    assert _keyword_classify("快递到哪里了").intent == "logistics"
    assert _keyword_classify("我要退款").intent == "refund"
    assert _keyword_classify("退货政策几天").intent == "policy"
    assert _keyword_classify("我要投诉").intent == "complaint"


def test_order_no_extracted() -> None:
    result = _keyword_classify("订单 CS2024002 到哪了")
    assert result.order_no == "CS2024002"


def test_policy_wins_over_refund_keyword() -> None:
    """回归测试：'退货政策' 同时含 '退货'，必须判成 policy。"""
    assert _keyword_classify("退货政策几天").intent == "policy"
    assert _keyword_classify("你们的退货政策是几天").intent == "policy"


def test_refund_variants() -> None:
    assert _keyword_classify("帮我把 CS2024003 退了").intent == "refund"
    assert _keyword_classify("这双鞋想退掉").intent == "refund"


def test_route_complaint_goes_to_handoff() -> None:
    assert route_after_classify({"intent": "complaint"}) == "handoff"
    assert route_after_classify({"intent": "logistics"}) == "tools"
    assert route_after_classify({"intent": "policy"}) == "respond"
    assert route_after_classify({"intent": "other"}) == "respond"


def test_handoff_prepare_writes_reply_before_interrupt() -> None:
    """回归测试：转人工前必须先把答复写进状态，否则用户看到空回复。"""
    out = asyncio.run(
        handoff_prepare(
            {
                "messages": [HumanMessage(content="我要投诉，客服一直不回复")],
                "thread_id": "t-test",
                "intent": "complaint",
            }
        )
    )
    assert out["needs_human"] is True
    assert "人工" in out["reply"]
