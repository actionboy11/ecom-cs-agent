from __future__ import annotations

from app.graph.react import _candidate_selection

CANDIDATES = [
    {"orderNo": "CS2024231", "createdAt": "2026-10-28", "deliveredAt": None},
    {"orderNo": "CS2024232", "createdAt": "2026-10-29", "deliveredAt": None},
    {"orderNo": "CS2024230", "createdAt": "2026-10-27", "deliveredAt": None},
]


def test_select_by_date() -> None:
    assert _candidate_selection("10月28号是那个", CANDIDATES) == "CS2024231"


def test_select_by_ordinal() -> None:
    assert _candidate_selection("第二个吧", CANDIDATES) == "CS2024232"


def test_select_explicit_order() -> None:
    assert _candidate_selection("选择订单 CS2024230", CANDIDATES) == "CS2024230"


def test_ambiguous_date_returns_none() -> None:
    candidates = CANDIDATES + [{"orderNo": "CS2024233", "createdAt": "2026-10-28"}]
    assert _candidate_selection("10月28号", candidates) is None
