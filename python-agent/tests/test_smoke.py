"""冒烟测试：不依赖任何 API Key 也能跑。

原则：脚手架必须先「无外部依赖可跑通」，否则 D1 会被环境问题拖死。
"""

from app.graph.builder import build_graph
from app.graph.nodes import _keyword_classify, route_after_classify


def test_graph_builds() -> None:
    graph = build_graph()
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


def test_route_complaint_goes_to_handoff() -> None:
    assert route_after_classify({"intent": "complaint"}) == "handoff"
    assert route_after_classify({"intent": "logistics"}) == "tools"
    assert route_after_classify({"intent": "policy"}) == "knowledge"
    assert route_after_classify({"intent": "other"}) == "respond"
