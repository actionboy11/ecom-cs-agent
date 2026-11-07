"""仓库内固定路径。

所有相对路径统一以仓库根为基准，避免从不同工作目录启动时读写到第二个位置。
"""

from __future__ import annotations

import os
from pathlib import Path

# paths.py -> app -> python-agent -> 仓库根
REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_under_repo(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def resolve_trace_dir(path: str | None = None) -> Path:
    return resolve_under_repo(path or os.getenv("TRACE_DIR", "traces"))
