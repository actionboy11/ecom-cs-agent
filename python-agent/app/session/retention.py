"""会话数据保留策略（TTL）。

清理范围（ADR-0005 / SPEC §5.5）：
- `thread_owner` 中超过保留期的行
- 这些 thread 对应的 `checkpoints` / `writes`
- 没有归属记录的遗留 checkpoint（#13 之前的会话，已不可用）
- `traces/*.jsonl` 中超过保留期的文件

注意：业务审计在 MySQL，不在这里，也不会被清理。
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path

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

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _count(conn: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def purge_expired(
    db_path: str | Path,
    traces_dir: str | Path | None = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
    dry_run: bool = False,
) -> PurgeResult:
    result = PurgeResult(ttl_days=ttl_days, dry_run=dry_run)
    path = Path(db_path)
    traces = Path(traces_dir or os.getenv("TRACE_DIR", "traces"))

    if path.exists():
        conn = sqlite3.connect(path)
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
                    # 归属表还不存在（#13 刚升级上来）：所有 checkpoint 都是无主遗留
                    orphans = [
                        r[0] for r in conn.execute("SELECT DISTINCT thread_id FROM checkpoints")
                    ]

            result.expired_threads = len(expired)
            result.orphan_threads = len(orphans)

            # 待删 thread：过期归属 + 无主遗留
            doomed = expired + [t for t in orphans if t not in expired]
            if doomed and dry_run:
                marks = ",".join("?" for _ in doomed)
                if "checkpoints" in tables:
                    result.checkpoints = _count(
                        conn, f"SELECT COUNT(*) FROM checkpoints WHERE thread_id IN ({marks})", tuple(doomed)
                    )
                if "writes" in tables:
                    result.writes = _count(
                        conn, f"SELECT COUNT(*) FROM writes WHERE thread_id IN ({marks})", tuple(doomed)
                    )
            elif doomed:
                marks = ",".join("?" for _ in doomed)
                if "checkpoints" in tables:
                    result.checkpoints = conn.execute(
                        f"DELETE FROM checkpoints WHERE thread_id IN ({marks})", tuple(doomed)
                    ).rowcount
                if "writes" in tables:
                    result.writes = conn.execute(
                        f"DELETE FROM writes WHERE thread_id IN ({marks})", tuple(doomed)
                    ).rowcount
                if expired:
                    marks = ",".join("?" for _ in expired)
                    conn.execute(f"DELETE FROM thread_owner WHERE thread_id IN ({marks})", tuple(expired))
                conn.commit()
        finally:
            conn.close()

    if traces.is_dir():
        cutoff_ts = time.time() - ttl_days * 86400
        for f in sorted(traces.glob("*.jsonl")):
            try:
                if f.stat().st_mtime < cutoff_ts:
                    result.traces += 1
                    if not dry_run:
                        f.unlink()
            except FileNotFoundError:
                continue

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="清理过期的 Agent 会话数据")
    parser.add_argument("--db", default=os.getenv("AGENT_STATE_DB", "data/agent_state.db"))
    parser.add_argument("--traces", default=os.getenv("TRACE_DIR", "traces"))
    parser.add_argument("--ttl-days", type=int, default=int(os.getenv("SESSION_TTL_DAYS", DEFAULT_TTL_DAYS)))
    parser.add_argument("--dry-run", action="store_true", help="只报告，不删除")
    args = parser.parse_args()

    result = purge_expired(args.db, args.traces, args.ttl_days, args.dry_run)
    print(json.dumps(result.as_dict(), ensure_ascii=False))


if __name__ == "__main__":
    main()
