"""评测用的引用指标。

区分两件事：
- `retrieval_hit`：检索到的主依据是否正确（衡量检索）
- `citation_hit`：**回答正文**里是否引用了预期条目（衡量回答，票面要求的就是这个）
"""

from __future__ import annotations

import re

_CITE = re.compile(r"\[(P\d{2})\]")


def extract_citations(text: str) -> list[str]:
    """按出现顺序去重抽取回复里的引用编号。"""
    seen: list[str] = []
    for pid in _CITE.findall(text or ""):
        if pid not in seen:
            seen.append(pid)
    return seen


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 3) if total else None


def is_citation_hit(row: dict) -> bool:
    """唯一命中判定：期望编号出现在回答引用里。报告与统计共用这一处。"""
    return bool(row.get("citation_expected")) and row["citation_expected"] in (row.get("citations") or [])


def citation_stats(rows: list[dict]) -> dict:
    """按用例统计：回答引用命中率 + 检索命中率 + 错例。

    分母只算标注了 `citation_expected` 的用例（政策类）。
    命中规则：期望编号出现在对应列表里即算命中（允许多引用）。
    """
    judged = [r for r in rows if r.get("citation_expected")]

    def _hits(field: str) -> int:
        return sum(1 for r in judged if r["citation_expected"] in (r.get(field) or []))

    citation_hits = sum(1 for r in judged if is_citation_hit(r))
    retrieval_hits = _hits("policy_refs")

    return {
        "citation_cases": len(judged),
        "citation_hits": citation_hits,
        "citation_hit_rate": _rate(citation_hits, len(judged)),
        "retrieval_hits": retrieval_hits,
        "retrieval_hit_rate": _rate(retrieval_hits, len(judged)),
        "citation_mismatches": [
            {
                "id": r["id"],
                "expected": r["citation_expected"],
                "actual": r.get("citations") or [],
                "retrieved": r.get("policy_refs") or [],
            }
            for r in judged
            if not is_citation_hit(r)
        ],
    }
