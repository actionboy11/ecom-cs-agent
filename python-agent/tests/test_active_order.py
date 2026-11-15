from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.graph.react import ACTIVE_ORDER_TTL, _active_order


def test_active_order_fresh() -> None:
    now = datetime.now(UTC).isoformat()
    assert _active_order({"active_order_no": "CS2024101", "active_order_at": now}) == "CS2024101"


def test_active_order_expires() -> None:
    stale = (datetime.now(UTC) - ACTIVE_ORDER_TTL - timedelta(seconds=1)).isoformat()
    assert _active_order({"active_order_no": "CS2024101", "active_order_at": stale}) is None


def test_active_order_without_timestamp() -> None:
    assert _active_order({"active_order_no": "CS2024101"}) is None
