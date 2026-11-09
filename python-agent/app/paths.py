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


def ensure_writable_temp() -> Path:
    """把 TMP/TEMP/TMPDIR 指向仓库内 .tmp。

    本机系统临时目录对子进程不可写（甚至探测时会阻塞），Chroma 的 Rust SQLite
    因此报 `unable to open database file (code 14)`；直接改指仓库内目录，
    既避开权限问题，也避免运行时再去探测系统临时目录。
    """
    base = REPO_ROOT / ".tmp"
    base.mkdir(parents=True, exist_ok=True)
    for var in ("TMP", "TEMP", "TMPDIR"):
        os.environ[var] = str(base)
    return base
