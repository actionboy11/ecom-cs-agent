from __future__ import annotations

import pytest

from app.config import settings
from app.graph import nodes
from app.nlp import catalog
from app.nlp.product_match import CatalogEntity


def test_catalog_from_products_includes_canonical_name_and_aliases() -> None:
    entities = catalog.from_products(
        [
            {
                "sku": "SKU1002",
                "name": "主动降噪蓝牙耳机",
                "canonical": "耳机",
                "aliases": ["蓝牙耳机", "降噪耳机"],
            }
        ]
    )
    assert entities[0].canonical == "耳机"
    assert set(entities[0].names) == {"耳机", "主动降噪蓝牙耳机", "蓝牙耳机", "降噪耳机"}


@pytest.mark.asyncio
async def test_catalog_uses_cache_when_fetch_fails(monkeypatch) -> None:
    catalog.reset_catalog_cache()

    async def ok():
        return [{"name": "主动降噪蓝牙耳机", "canonical": "耳机", "aliases": ["耳机"]}]

    monkeypatch.setattr(catalog.business_api, "list_products", ok)
    first = await catalog.load_catalog(force=True)
    assert first

    async def fail():
        raise RuntimeError("UNAVAILABLE")

    monkeypatch.setattr(catalog.business_api, "list_products", fail)
    second = await catalog.load_catalog(force=True)
    assert second == first
    catalog.reset_catalog_cache()


def test_hard_rule_product_and_order_cue_becomes_order_query() -> None:
    entities = (CatalogEntity("耳机", ("蓝牙耳机", "耳机")),)
    assert nodes._apply_hard_rules("蓝牙而机这个订单", "other", entities) == "order_query"


def test_hard_rule_product_and_missing_cue_becomes_logistics() -> None:
    entities = (CatalogEntity("耳机", ("蓝牙耳机", "耳机")),)
    assert nodes._apply_hard_rules("蓝牙而机 咋还没到", "other", entities) == "logistics"


def test_compound_does_not_trigger_hard_rule() -> None:
    entities = (CatalogEntity("耳机", ("蓝牙耳机", "耳机")),)
    assert nodes._apply_hard_rules("耳机套", "other", entities) == "other"


def test_other_with_matched_product_routes_to_react(monkeypatch) -> None:
    monkeypatch.setattr(settings, "react_enabled", True)
    state = {"intent": "other", "matched_products": ["耳机"], "turn_count": 1, "refusal": None}
    assert nodes.route_after_classify(state) == "react"  # type: ignore[arg-type]


def test_other_without_product_stays_respond(monkeypatch) -> None:
    monkeypatch.setattr(settings, "react_enabled", True)
    state = {"intent": "other", "matched_products": [], "turn_count": 1, "refusal": None}
    assert nodes.route_after_classify(state) == "respond"  # type: ignore[arg-type]


def test_last_candidates_routes_to_react(monkeypatch) -> None:
    monkeypatch.setattr(settings, "react_enabled", True)
    state = {
        "intent": "other",
        "matched_products": [],
        "last_candidates": [{"orderNo": "CS2024231"}],
        "turn_count": 2,
        "refusal": None,
    }
    assert nodes.route_after_classify(state) == "react"  # type: ignore[arg-type]
