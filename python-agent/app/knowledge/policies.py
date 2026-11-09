"""政策库：解析 `data/policies/policies.md`，并提供关键词兜底检索。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.paths import resolve_under_repo

_HEADING = re.compile(r"^##\s+(P\d{2})\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Policy:
    policy_id: str
    title: str
    body: str

    def as_document(self) -> str:
        return f"[{self.policy_id}] {self.title}\n{self.body}"


def load_policies(path: str | Path | None = None) -> list[Policy]:
    file = resolve_under_repo(path or "data/policies/policies.md")
    text = Path(file).read_text(encoding="utf-8")
    matches = list(_HEADING.finditer(text))
    policies: list[Policy] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        policies.append(Policy(m.group(1), m.group(2).strip(), text[m.end() : end].strip()))
    return policies


def _grams(text: str) -> set[str]:
    return {text[i : i + 2] for i in range(len(text) - 1)}


def keyword_search(query: str, k: int = 3, policies: list[Policy] | None = None) -> list[Policy]:
    """无向量库时的兜底：按字符二元组重合度排序，确定性、无外部依赖。"""
    candidates = policies if policies is not None else load_policies()
    q = _grams(query)
    scored: list[tuple[int, Policy]] = []
    for p in candidates:
        score = len(q & _grams(p.title + p.body))
        if query and query in p.body:
            score += 5
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].policy_id))
    return [p for _, p in scored[:k]]
