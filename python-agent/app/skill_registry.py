"""加载 skills/*/SKILL.md：系统提示只暴露 name + description，命中后再读全文。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path


def _frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


@lru_cache(maxsize=1)
def all_skills() -> dict[str, Skill]:
    found: dict[str, Skill] = {}
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        meta = _frontmatter(path.read_text(encoding="utf-8"))
        name = meta.get("name", "").strip()
        description = meta.get("description", "").strip()
        if not name or not description:
            continue
        found[name] = Skill(name=name, description=description, path=path)
    return found


def descriptions() -> str:
    return "\n".join(f"- {skill.name}: {skill.description}" for skill in all_skills().values())


def load(name: str) -> str:
    skill = all_skills().get(name)
    if skill is None:
        raise ValueError(f"unknown skill: {name}")
    return skill.path.read_text(encoding="utf-8")
