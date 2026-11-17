from __future__ import annotations

from datetime import date

from app import clock
from app.config import settings
from app.graph.time_refs import parse_time_reference


def test_eval_today_freezes_clock(monkeypatch) -> None:
    monkeypatch.setattr(settings, "eval_today", "2026-11-15")
    assert clock.today() == date(2026, 11, 15)
    assert clock.now().date() == date(2026, 11, 15)


def test_relative_time_uses_eval_today(monkeypatch) -> None:
    monkeypatch.setattr(settings, "eval_today", "2026-11-15")
    first = parse_time_reference("昨天买的")
    monkeypatch.setattr(settings, "eval_today", "2026-11-16")
    second = parse_time_reference("昨天买的")
    assert first is not None and second is not None
    assert first["from"] == "2026-11-14"
    assert second["from"] == "2026-11-15"
    assert first["from"] != second["from"]


def test_empty_eval_today_uses_real_clock(monkeypatch) -> None:
    monkeypatch.setattr(settings, "eval_today", "")
    assert clock.today() == date.today()


def test_day_only_time_reference(monkeypatch) -> None:
    monkeypatch.setattr(settings, "eval_today", "2026-11-15")
    delivered = parse_time_reference("12号收到")
    created = parse_time_reference("4号买的")
    assert delivered is not None and delivered["field"] == "delivered"
    assert delivered["from"] == "2026-11-12"
    assert created is not None and created["field"] == "created"
    assert created["from"] == "2026-11-04"
