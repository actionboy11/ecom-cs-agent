"""仓库内固定路径。

所有相对路径统一以仓库根为基准，避免从不同工作目录启动时读写到第二个位置。
容器里 `/app/app/paths.py` 的 `parents[2]` 会指向 `/`，因此优先用 `APP_ROOT`，
并且只有在仓库根确实存在 `data/policies` 时才认它，否则回落到当前工作目录。
"""

from __future__ import annotations

import os
from pathlib import Path


def _detect_root() -> Path:
    configured = os.getenv("APP_ROOT")
    if configured:
        return Path(configured).resolve()
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "data" / "policies").is_dir():
        return candidate
    return Path.cwd()


REPO_ROOT = _detect_root()


def resolve_under_repo(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def resolve_trace_dir(path: str | None = None) -> Path:
    return resolve_under_repo(path or os.getenv("TRACE_DIR", "traces"))


def ensure_writable_temp() -> Path:
    """把 TMP/TEMP/TMPDIR 指向仓库内 .tmp。

    本机系统临时目录对子进程不可写，Chroma 的 Rust SQLite 因此报
    `unable to open database file (code 14)`；直接改指工作目录内目录。
    """
    base = REPO_ROOT / ".tmp"
    base.mkdir(parents=True, exist_ok=True)
    for var in ("TMP", "TEMP", "TMPDIR"):
        os.environ[var] = str(base)
    return base
