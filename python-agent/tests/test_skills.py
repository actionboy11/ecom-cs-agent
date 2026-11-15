from __future__ import annotations

from datetime import date

import pytest

from app.skills import order_lookup, return_flow


@pytest.mark.asyncio
async def test_order_lookup_auto(monkeypatch) -> None:
    async def fake_find(*_args, **_kwargs):
        return [
            {"orderNo": "CS1", "score": 0.95, "item": "鞋"},
            {"orderNo": "CS2", "score": 0.60, "item": "鞋"},
        ]

    monkeypatch.setattr(order_lookup.business_api, "find_my_orders", fake_find)
    result = await order_lookup.order_lookup("token", product_terms=["鞋"])
    assert result["status"] == "auto"
    assert result["order_no"] == "CS1"


@pytest.mark.asyncio
async def test_order_lookup_ask(monkeypatch) -> None:
    async def fake_find(*_args, **_kwargs):
        return [
            {"orderNo": "CS1", "score": 0.95, "item": "鞋"},
            {"orderNo": "CS2", "score": 0.90, "item": "鞋"},
        ]

    monkeypatch.setattr(order_lookup.business_api, "find_my_orders", fake_find)
    result = await order_lookup.order_lookup("token", product_terms=["鞋"])
    assert result["status"] == "ask"
    assert len(result["candidates"]) == 2


@pytest.mark.asyncio
async def test_order_lookup_none(monkeypatch) -> None:
    async def fake_find(*_args, **_kwargs):
        return []

    monkeypatch.setattr(order_lookup.business_api, "find_my_orders", fake_find)
    result = await order_lookup.order_lookup("token", product_terms=["镜子"])
    assert result["status"] == "none"


def _order(tags: str = "", status: str = "已签收", delivered: str = "2026-11-10T15:00:00"):
    return {"orderNo": "CS1", "status": status, "tags": tags, "deliveredAt": delivered}


@pytest.mark.asyncio
async def test_normal_return_custom_redirects(monkeypatch) -> None:
    async def fake_get(*_args, **_kwargs):
        return _order(tags="custom")

    monkeypatch.setattr(return_flow.business_api, "get_order", fake_get)
    result = await return_flow.normal_return("token", "CS1", "不想要了", today=date(2026, 11, 15))
    assert result["status"] == "wrong_skill"


@pytest.mark.asyncio
async def test_normal_return_out_of_window(monkeypatch) -> None:
    async def fake_get(*_args, **_kwargs):
        return _order(delivered="2026-10-01T15:00:00")

    monkeypatch.setattr(return_flow.business_api, "get_order", fake_get)
    result = await return_flow.normal_return("token", "CS1", "不想要了", today=date(2026, 11, 15))
    assert result["status"] == "out_of_window"


@pytest.mark.asyncio
async def test_normal_return_ready_quality(monkeypatch) -> None:
    async def fake_get(*_args, **_kwargs):
        return _order(delivered="2026-11-12T15:00:00")

    monkeypatch.setattr(return_flow.business_api, "get_order", fake_get)
    result = await return_flow.normal_return("token", "CS1", "鞋子开线", today=date(2026, 11, 15))
    assert result["status"] == "ready"
    assert result["policy"] == "P02"
    assert result["as_type"] == "RETURN"


@pytest.mark.asyncio
async def test_custom_return_handoff_without_quality(monkeypatch) -> None:
    async def fake_get(*_args, **_kwargs):
        return _order(tags="custom")

    monkeypatch.setattr(return_flow.business_api, "get_order", fake_get)
    result = await return_flow.custom_return("token", "CS1", "不想要了", today=date(2026, 11, 15))
    assert result["status"] == "handoff"


@pytest.mark.asyncio
async def test_custom_return_quality_ready(monkeypatch) -> None:
    async def fake_get(*_args, **_kwargs):
        return _order(tags="custom", delivered="2026-11-10T15:00:00")

    monkeypatch.setattr(return_flow.business_api, "get_order", fake_get)
    result = await return_flow.custom_return("token", "CS1", "开线了", today=date(2026, 11, 15))
    assert result["status"] == "ready"
    assert result["policy"] == "P02"
