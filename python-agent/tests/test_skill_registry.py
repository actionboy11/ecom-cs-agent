from __future__ import annotations

import pytest

from app import skill_registry
from app.graph.react import _build_tools


def test_three_skills_are_discovered() -> None:
    names = set(skill_registry.all_skills())
    assert names == {"order-lookup", "normal-return", "custom-return"}


def test_descriptions_do_not_contain_full_steps() -> None:
    text = skill_registry.descriptions()
    assert "order-lookup" in text
    assert "## 步骤" not in text


def test_load_returns_full_document() -> None:
    text = skill_registry.load("normal-return")
    assert "## 步骤" in text
    assert "create_return" in text


def test_unknown_skill_raises() -> None:
    with pytest.raises(ValueError):
        skill_registry.load("../etc/passwd")


def test_load_skill_tool_is_registered() -> None:
    tools = _build_tools("token", "thread")
    assert "load_skill" in {tool.name for tool in tools}
