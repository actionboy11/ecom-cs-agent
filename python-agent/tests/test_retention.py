"""S3-3：会话 TTL。

验证：
1. 过期 thread 的归属、checkpoint、writes 被删除，未过期的不受影响；
2. `--dry-run` 只统计不删除；
3. 无主遗留 checkpoint 被清理；
4. 轨迹按文件名日期清理（不依赖 mtime）；
5. CLI 在状态库缺失时返回非零退出码。
"""

from __future__ import annotations

import sqlite3
import sys

import pytest
from langchain_core.messages import HumanMessage

from app.graph.builder import build_graph
from app.graph.checkpointer import sqlite_checkpointer
from app.session.retention import purge_expired
from app.session.thread_store import ThreadOwnerStore


async def _seed(db_path: str) -> None:
    store = await ThreadOwnerStore.open(db_path)
    await store.bind("t-old", 1)
    await store.bind("t-new", 2)
    await store.close()

    async with sqlite_checkpointer(db_path) as saver:
        graph = build_graph(saver)
        for thread in ("t-old", "t-new"):
            await graph.aupdate_state(
                {"configurable": {"thread_id": thread}},
                {"messages": [HumanMessage(content=f"{thread} 的消息")]},
            )

    conn = sqlite3.connect(db_path)
    # 制造一条写入中间态（writes 表在真实运行中会有行）
    conn.execute(
        "INSERT INTO writes (thread_id, checkpoint_ns, checkpoint_id, task_id, task_path, idx, channel, type, value) "
        "VALUES ('t-old', '', 'cp1', 'task1', '', 0, 'messages', 'json', 'null')"
    )
    # 把 t-old 的更新时间拨到 40 天前
    conn.execute(
        "UPDATE thread_owner SET updated_at = datetime('now', '-40 days') WHERE thread_id = 't-old'"
    )
    conn.commit()
    conn.close()


@pytest.mark.asyncio
async def test_only_expired_threads_are_purged(tmp_path) -> None:
    db_path = str(tmp_path / "state.db")
    await _seed(db_path)

    result = purge_expired(db_path, tmp_path / "traces", ttl_days=30)

    assert result.expired_threads == 1
    assert result.checkpoints >= 1
    assert result.writes == 1

    conn = sqlite3.connect(db_path)
    owners = {r[0] for r in conn.execute("SELECT thread_id FROM thread_owner")}
    checkpoints = {r[0] for r in conn.execute("SELECT DISTINCT thread_id FROM checkpoints")}
    writes = {r[0] for r in conn.execute("SELECT DISTINCT thread_id FROM writes")}
    conn.close()

    assert "t-old" not in owners
    assert "t-new" in owners
    assert "t-old" not in checkpoints
    assert "t-new" in checkpoints
    assert "t-old" not in writes


@pytest.mark.asyncio
async def test_dry_run_reports_without_deleting(tmp_path) -> None:
    db_path = str(tmp_path / "state.db")
    await _seed(db_path)

    result = purge_expired(db_path, tmp_path / "traces", ttl_days=30, dry_run=True)

    assert result.dry_run is True
    assert result.expired_threads == 1
    assert result.checkpoints >= 1
    assert result.writes == 1

    conn = sqlite3.connect(db_path)
    owners = {r[0] for r in conn.execute("SELECT thread_id FROM thread_owner")}
    checkpoints = {r[0] for r in conn.execute("SELECT DISTINCT thread_id FROM checkpoints")}
    writes = {r[0] for r in conn.execute("SELECT DISTINCT thread_id FROM writes")}
    conn.close()
    assert {"t-old", "t-new"} <= owners
    assert {"t-old", "t-new"} <= checkpoints
    assert "t-old" in writes


@pytest.mark.asyncio
async def test_orphan_checkpoints_without_owner_are_removed(tmp_path) -> None:
    db_path = str(tmp_path / "state.db")
    async with sqlite_checkpointer(db_path) as saver:
        graph = build_graph(saver)
        await graph.aupdate_state(
            {"configurable": {"thread_id": "t-orphan"}},
            {"messages": [HumanMessage(content="升级前的历史会话")]},
        )

    result = purge_expired(db_path, tmp_path / "traces", ttl_days=30)

    assert result.orphan_threads == 1
    conn = sqlite3.connect(db_path)
    checkpoints = {r[0] for r in conn.execute("SELECT DISTINCT thread_id FROM checkpoints")}
    conn.close()
    assert "t-orphan" not in checkpoints


def test_trace_files_are_purged_by_filename_date(tmp_path) -> None:
    traces = tmp_path / "traces"
    traces.mkdir()
    old = traces / "20250101.jsonl"  # 文件名日期很旧，但 mtime 是现在
    new = traces / "20261107.jsonl"
    old.write_text('{"node": "classify"}\n', encoding="utf-8")
    new.write_text('{"node": "respond"}\n', encoding="utf-8")

    result = purge_expired(tmp_path / "state.db", traces, ttl_days=30)

    assert result.traces == 1
    assert not old.exists()
    assert new.exists()


def test_cli_exits_nonzero_when_state_db_is_missing(tmp_path, monkeypatch) -> None:
    from app.session import retention

    monkeypatch.setattr(sys, "argv", ["cleanup", "--db", str(tmp_path / "missing.db")])
    with pytest.raises(SystemExit) as excinfo:
        retention.main()
    assert excinfo.value.code == 2


def test_ttl_must_be_positive(tmp_path) -> None:
    with pytest.raises(ValueError):
        purge_expired(tmp_path / "state.db", tmp_path / "traces", ttl_days=0)
