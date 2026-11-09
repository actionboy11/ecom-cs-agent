"""评测用的引用指标：从回复里抽取 `[Pxx]`，并按用例统计引用命中率。"""

from __future__ import annotations

import re

_CITE = re.compile(r"\[(P\d{2})\]")


def extract_citations(text: str) -> list[str]:
    """按出现顺序去重抽取引用编号。"""
    seen: list[str] = []
    for pid in _CITE.findall(text or ""):
        if pid not in seen:
            seen.append(pid)
    return seen


def citation_stats(rows: list[dict]) -> dict:
    """rows 里每项需要 `citation_expected`（可为空）与 `citations`（实际引用列表）。

    命中规则：期望编号出现在实际引用里即算命中（允许多引用）。
    """
    judged = [r for r in rows if r.get("citation_expected")]
    hits = [r for r in judged if r["citation_expected"] in (r.get("citations") or [])]
    mismatches = [
        {
            "id": r["id"],
            "expected": r["citation_expected"],
            "actual": r.get("citations") or [],
        }
        for r in judged
        if r["citation_expected"] not in (r.get("citations") or [])
    ]
    return {
        "citation_cases": len(judged),
        "citation_hits": len(hits),
        "citation_hit_rate": round(len(hits) / len(judged), 3) if judged else None,
        "citation_mismatches": mismatches,
    }
