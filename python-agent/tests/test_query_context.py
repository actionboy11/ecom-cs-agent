from __future__ import annotations

from app.graph.query_context import QueryContext, infer_action, resolve_candidate

CANDIDATES = [
    {"orderNo": "CS2024231", "createdAt": "2026-10-28", "deliveredAt": None, "status": "待发货"},
    {"orderNo": "CS2024232", "createdAt": "2026-10-29", "deliveredAt": None, "status": "待发货"},
]


def test_infer_action_ignores_policy_question() -> None:
    assert infer_action("这单能退吗") is None
    assert infer_action("这个能换吗") is None


def test_infer_action_accepts_explicit_request() -> None:
    assert infer_action("我要退货") == "return"
    assert infer_action("帮我换个颜色") == "exchange"
    assert infer_action("帮我催一下") == "urge"


def test_context_applies_delivered_time() -> None:
    ctx = QueryContext(time_field="delivered", time_from="2026-11-14", time_to="2026-11-14")
    args = ctx.apply_find_args({"product_terms": ["充电宝"]})
    assert args["delivered_from"] == "2026-11-14"
    assert args["delivered_to"] == "2026-11-14"
    assert "created_from" not in args


def test_resolve_candidate_by_date() -> None:
    assert resolve_candidate("10月28号那单", CANDIDATES) == "CS2024231"


def test_resolve_candidate_ambiguous_date() -> None:
    candidates = CANDIDATES + [{"orderNo": "CS2024233", "createdAt": "2026-10-28"}]
    assert resolve_candidate("10月28号", candidates) is None
