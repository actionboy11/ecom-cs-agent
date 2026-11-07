"""会话数据保留策略（TTL）。

清理范围（ADR-0005 / SPEC §5.5）：
- `thread_owner` 中超过保留期的行
- 这些 thread 对应的 `checkpoints` / `writes`
- 没有归属记录的遗留 checkpoint（#13 之前的会话，已不可用）
- `traces/*.jsonl` 中超过保留期的文件（优先按文件名日期，退化到 mtime）

注意：业务审计在 MySQL，不在这里，也不会被清理。

CLI 入口：`python -m app.maintenance.cleanup --dry-run`
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from app.graph.checkpointer import resolve_db_path
from app.paths import resolve_trace_dir

DEFAULT_TTL_DAYS = 30


@dataclass
class PurgeResult:
    ttl_days: int
    dry_run: bool
    expired_threads: int = 0
    orphan_threads: int = 0
    checkpoints: int = 0
    writes: int = 0
    traces: int = 0
    failures: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _count(conn: sqlite3.Connection, table: str, doomed: list[str]) -> int:
    marks = ",".join("?" for _ in doomed)
    return int(
        conn.execute(f"SELECT COUNT(*) FROM {table} WHERE thread_id IN ({marks})", tuple(doomed)).fetchone()[0]
    )


def _purge_db(db_path: Path, ttl_days: int, dry_run: bool) -> PurgeResult:
    result = PurgeResult(ttl_days=ttl_days, dry_run=dry_run)
    conn = sqlite3.connect(db_path)
    try:
        tables = _tables(conn)
        cutoff = f"-{int(ttl_days)} days"

        expired: list[str] = []
        if "thread_owner" in tables:
            expired = [
                r[0]
                for r in conn.execute(
                    "SELECT thread_id FROM thread_owner WHERE updated_at < datetime('now', ?)",
                    (cutoff,),
                )
            ]

        orphans: list[str] = []
        if "checkpoints" in tables:
            if "thread_owner" in tables:
                orphans = [
                    r[0]
                    for r in conn.execute(
                        "SELECT DISTINCT thread_id FROM checkpoints "
                        "WHERE thread_id NOT IN (SELECT thread_id FROM thread_owner)"
                    )
                ]
            else:
                orphans = [r[0] for r in conn.execute("SELECT DISTINCT thread_id FROM checkpoints")]

        result.expired_threads = len(expired)
        result.orphan_threads = len(orphans)

        doomed = expired + [t for t in orphans if t not in expired]
        if doomed:
            targets = [t for t in ("checkpoints", "writes") if t in tables]
            if dry_run:
                for table in targets:
                    setattr(result, table, _count(conn, table, doomed))
            else:
                marks = ",".join("?" for _ in doomed)
                for table in targets:
                    setattr(
                        result,
                        table,
                        conn.execute(f"DELETE FROM {table} WHERE thread_id IN ({marks})", tuple(doomed)).rowcount,
                    )
                if expired:
                    marks = ",".join("?" for _ in expired)
                    conn.execute(f"DELETE FROM thread_owner WHERE thread_id IN ({marks})", tuple(expired))
                conn.commit()
    finally:
        conn.close()
    return result


def _trace_date(path: Path) -> float:
    """优先用文件名里的 YYYYMMDD 判断日期；解析不了再看 mtime。"""
    try:
        return datetime.strptime(path.stem, "%Y%m%d").timestamp()
    except ValueError:
        return path.stat().st_mtime


def _purge_traces(traces: Path, ttl_days: int, dry_run: bool) -> tuple[int, int]:
    """返回 (删除数, 失败数)。"""
    if not traces.is_dir():
        return 0, 0
    cutoff_ts = time.time() - ttl_days * 86400
    removed = failed = 0
    for f in sorted(traces.glob("*.jsonl")):
        try:
            if _trace_date(f) >= cutoff_ts:
                continue
            if not dry_run:
                f.unlink()
            removed += 1
        except FileNotFoundError:
            continue
        except OSError:
            failed += 1
    return removed, failed


def purge_expired(
    db_path: str | Path,
    traces_dir: str | Path | None = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
    dry_run: bool = False,
) -> PurgeResult:
    if ttl_days < 1:
        raise ValueError("ttl_days 必须 >= 1")

    path = resolve_db_path(str(db_path))
    traces = resolve_trace_dir(str(traces_dir) if traces_dir else None)

    result = PurgeResult(ttl_days=ttl_days, dry_run=dry_run)
    if path.exists():
        result = _purge_db(path, ttl_days, dry_run)

    result.traces, failed = _purge_traces(traces, ttl_days, dry_run)
    result.failures = failed
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="清理过期的 Agent 会话数据（SPEC §5.5）")
    parser.add_argument("--db", default=None, help="状态库路径（默认 data/agent_state.db，相对仓库根）")
    parser.add_argument("--traces", default=None, help="轨迹目录（默认 traces/，相对仓库根）")
    parser.add_argument("--ttl-days", type=int, default=DEFAULT_TTL_DAYS)
    parser.add_argument("--dry-run", action="store_true", help="只报告，不删除")
    args = parser.parse_args()

    if args.ttl_days < 1:
        print("ttl_days 必须 >= 1", file=sys.stderr)
        raise SystemExit(2)

    db = resolve_db_path(args.db or "data/agent_state.db")
    if not db.exists():
        print(f"状态库不存在: {db}", file=sys.stderr)
        raise SystemExit(2)

    try:
        result = purge_expired(db, args.traces, args.ttl_days, args.dry_run)
    except Exception as exc:  # noqa: BLE001 - CLI 必须给出非零退出码
        print(f"清理失败: {exc}", file=sys.stderr)
        raise SystemExit(3) from exc

    print(json.dumps(result.as_dict(), ensure_ascii=False))
    if result.failures:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
