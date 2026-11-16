"""商品目录加载：Java /api/products/search → CatalogEntity，带 TTL 和最近缓存。"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.nlp.product_match import CatalogEntity
from app.tools import business_api

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300
_cached: tuple[CatalogEntity, ...] | None = None
_cached_at = 0.0


def from_products(products: list[dict[str, Any]]) -> tuple[CatalogEntity, ...]:
    entities: list[CatalogEntity] = []
    seen: set[str] = set()
    for product in products:
        canonical = str(product.get("canonical") or product.get("name") or "").strip()
        if not canonical or canonical in seen:
            continue
        names: list[str] = [canonical]
        name = str(product.get("name") or "").strip()
        if name:
            names.append(name)
        for alias in product.get("aliases") or []:
            alias = str(alias).strip()
            if alias:
                names.append(alias)
        entities.append(CatalogEntity(canonical=canonical, names=tuple(dict.fromkeys(names))))
        seen.add(canonical)
    return tuple(entities)


def reset_catalog_cache() -> None:
    global _cached, _cached_at
    _cached = None
    _cached_at = 0.0


async def load_catalog(force: bool = False) -> tuple[CatalogEntity, ...]:
    global _cached, _cached_at
    now = time.monotonic()
    if not force and _cached is not None and now - _cached_at < CACHE_TTL_SECONDS:
        return _cached
    try:
        products = await business_api.list_products()
        _cached = from_products(products)
        _cached_at = now
        return _cached
    except Exception as exc:  # noqa: BLE001 - 目录失败不能阻塞主流程
        logger.warning("商品目录加载失败，使用最近缓存: %s", str(exc)[:200])
        return _cached or ()
