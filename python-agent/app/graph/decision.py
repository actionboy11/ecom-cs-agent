"""用户回合的唯一决策：回答 / 澄清 / 表单 / 确认 / 拦截 / 转人工 / 拒答。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DecisionKind = Literal[
    "answer", "clarify", "form", "confirm", "intercept", "handoff", "refuse"
]


@dataclass
class Decision:
    kind: DecisionKind
    text: str = ""
    action: str | None = None
    order_no: str | None = None
    reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
