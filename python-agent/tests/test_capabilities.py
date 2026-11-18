from __future__ import annotations

from app.config import settings
from app.graph import capabilities


def test_address_is_user_action() -> None:
    result = capabilities.detect("帮我把这个订单的地址改到公司")
    assert result is not None
    assert result.kind == "user_action_request"
    assert result.payload["action"] == "change_address"


def test_invoice_is_user_action() -> None:
    result = capabilities.detect("给这个订单开发票")
    assert result is not None
    assert result.payload["action"] == "invoice"


def test_history_multiple_months(monkeypatch) -> None:
    monkeypatch.setattr(settings, "eval_today", "2026-11-15")
    result = capabilities.detect("10月、11月买了什么")
    assert result is not None
    assert result.kind == "order_history"
    assert result.payload["created_from"] == "2026-10-01"
    assert result.payload["created_to"] == "2026-11-15"
