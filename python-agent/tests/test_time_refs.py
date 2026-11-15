from __future__ import annotations

from datetime import date

from app.graph.time_refs import parse_time_reference


def test_yesterday_received_is_delivered_field() -> None:
    result = parse_time_reference("我昨天收到的耳机有问题", today=date(2026, 11, 15))
    assert result == {
        "field": "delivered",
        "from": "2026-11-14",
        "to": "2026-11-14",
        "label": "昨天",
    }


def test_last_week_created() -> None:
    result = parse_time_reference("上周买的鞋想退货", today=date(2026, 11, 15))
    assert result is not None
    assert result["field"] == "created"
    assert result["from"] == "2026-11-02"
    assert result["to"] == "2026-11-08"


def test_last_month_range() -> None:
    result = parse_time_reference("上个月买的杯子漏水", today=date(2026, 11, 15))
    assert result is not None
    assert result["from"] == "2026-10-01"
    assert result["to"] == "2026-10-31"


def test_recent_days() -> None:
    result = parse_time_reference("最近3天有订单吗", today=date(2026, 11, 15))
    assert result is not None
    assert result["from"] == "2026-11-13"
    assert result["to"] == "2026-11-15"


def test_unknown_time_returns_none() -> None:
    assert parse_time_reference("耳机多少钱", today=date(2026, 11, 15)) is None
