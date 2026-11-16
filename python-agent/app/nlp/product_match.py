"""商品实体链接：目录精确匹配 + 同长度错别字 + NIL/派生词保护。

只做 mention 识别，不选订单、不改路由。
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from functools import lru_cache

from pypinyin import Style, lazy_pinyin

TYPO_CHAR_RATIO = 0.75
TYPO_PINYIN_CHAR_RATIO = 0.5
MAX_SCORE = 1.0

# 通用边界：这些字出现在商品名旁边时，说明是谓词/修饰/分隔，不构成派生词。
# 不包含「套/壳/膜/配件」等具体后缀——派生词判断靠长度和边界，不靠商品词表。
ALLOWED_NEIGHBOR = set(
    "的了是吗呢吧和与及或、，,。；;！!？? \t\n"
    "查问看帮我想买退换订单物流快递发货收签款货到哪多少钱怎么可以是有请给找下一这个那"
)

@dataclass(frozen=True)
class CatalogEntity:
    canonical: str
    names: tuple[str, ...]


DEFAULT_CATALOG: tuple[CatalogEntity, ...] = (
    CatalogEntity("耳机", ("蓝牙耳机", "降噪耳机", "无线耳机", "耳机", "耳麦")),
    CatalogEntity("保温杯", ("保温杯", "水杯", "杯子", "杯")),
    CatalogEntity("跑步鞋", ("跑步鞋", "跑鞋", "运动鞋", "鞋")),
    CatalogEntity("行李箱", ("行李箱", "登机箱", "箱子", "拉杆箱")),
    CatalogEntity("背包", ("背包", "双肩包")),
    CatalogEntity("充电宝", ("充电宝", "移动电源")),
)


@dataclass(frozen=True)
class Candidate:
    canonical: str
    alias: str
    start: int
    end: int
    score: float
    method: str


@lru_cache(maxsize=512)
def _pinyin(text: str) -> str:
    return "".join(lazy_pinyin(text, style=Style.NORMAL))


def _ratio(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, left, right).ratio()


def _is_chinese(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def _boundary_ok(text: str, start: int, end: int) -> bool:
    left_ok = start == 0 or not _is_chinese(text[start - 1]) or text[start - 1] in ALLOWED_NEIGHBOR
    right_ok = end == len(text) or not _is_chinese(text[end]) or text[end] in ALLOWED_NEIGHBOR
    return left_ok and right_ok


def _compound_span(text: str, start: int, end: int) -> tuple[int, int]:
    left, right = start, end
    while left > 0 and _is_chinese(text[left - 1]) and text[left - 1] not in ALLOWED_NEIGHBOR:
        left -= 1
    while right < len(text) and _is_chinese(text[right]) and text[right] not in ALLOWED_NEIGHBOR:
        right += 1
    return left, right


def _candidates(text: str, catalog: tuple[CatalogEntity, ...]) -> list[Candidate]:
    found: list[Candidate] = []
    for entity in catalog:
        for alias in entity.names:
            length = len(alias)
            for start in range(len(text) - length + 1):
                window = text[start : start + length]
                if window == alias:
                    found.append(Candidate(entity.canonical, alias, start, start + length, 1.0, "exact"))
                    continue
                ratio = _ratio(alias, window)
                pinyin_equal = _pinyin(alias) == _pinyin(window)
                same = sum(1 for a, b in zip(alias, window) if a == b)
                if ratio >= TYPO_CHAR_RATIO:
                    found.append(Candidate(entity.canonical, alias, start, start + length, ratio, "typo"))
                elif (
                    pinyin_equal
                    and ratio >= TYPO_PINYIN_CHAR_RATIO
                    and (same >= 2 if length >= 3 else window[0] == alias[0])
                ):
                    found.append(Candidate(entity.canonical, alias, start, start + length, 0.95, "typo"))
    return found


def _select(candidates: list[Candidate]) -> list[Candidate]:
    chosen: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda c: (-(c.end - c.start), -c.score, c.start)):
        if any(candidate.start < other.end and other.start < candidate.end for other in chosen):
            continue
        chosen.append(candidate)
    return sorted(chosen, key=lambda c: c.start)


def match_products(text: str, catalog: tuple[CatalogEntity, ...] | None = None) -> dict:
    matches: list[dict] = []
    unknown: list[dict] = []
    for candidate in _select(_candidates(text, catalog or DEFAULT_CATALOG)):
        if _boundary_ok(text, candidate.start, candidate.end):
            matches.append(
                {
                    "canonical": candidate.canonical,
                    "surface": text[candidate.start : candidate.end],
                    "span": [candidate.start, candidate.end],
                    "method": candidate.method,
                    "score": round(candidate.score, 3),
                }
            )
            continue
        start, end = _compound_span(text, candidate.start, candidate.end)
        if any(item["span"][0] == start and item["span"][1] == end for item in unknown):
            continue
        unknown.append(
            {
                "surface": text[start:end],
                "span": [start, end],
                "reason": "noun_phrase_not_in_catalog",
            }
        )

    return {"matches": matches, "unknown": unknown, "ambiguous": []}
