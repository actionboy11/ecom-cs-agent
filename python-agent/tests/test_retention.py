"""S3-3：会话 TTL。

验证三件事：
1. 过期 thread 的归属与 checkpoint 被删除，未过期的不受影响；
2. `--dry-run` 只统计不删除；
3. 过期轨迹文件被清理，新文件保留。
"""

from __future__ import annotations

import os
import sqlite3
import time

import pytest
from langchain_core.messages import HumanMessage

from app.graph.builder import build_graph
from app.graph.checkpointer import sqlite_checkpointer
from app.session.retention import purge_expired
from app.session.thread_store import ThreadOwnerStore


async def _seed(db_path: str, traces_dir) -> None:
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

    # 把 t-old 的更新时间拨到 40 天前
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE thread_owner SET updated_at = datetime('now', '-40 days') WHERE thread_id = 't-old'"
    )
    conn.commit()
    conn.close()


@pytest.mark.asyncio
async def test_only_expired_threads_are_purged(tmp_path) -> None:
    db_path = str(tmp_path / "state.db")
    await _seed(db_path, tmp_path / "traces")

    result = purge_expired(db_path, tmp_path / "traces", ttl_days=30)

    assert result.expired_threads == 1
    assert result.checkpoints >= 1

    conn = sqlite3.connect(db_path)
    owners = {r[0] for r in conn.execute("SELECT thread_id FROM thread_owner")}
    checkpoints = {r[0] for r in conn.execute("SELECT DISTINCT thread_id FROM checkpoints")}
    conn.close()

    assert "t-old" not in owners
    assert "t-new" in owners
    assert "t-old" not in checkpoints
    assert "t-new" in checkpoints


@pytest.mark.asyncio
async def test_dry_run_reports_without_deleting(tmp_path) -> None:
    db_path = str(tmp_path / "state.db")
    await _seed(db_path, tmp_path / "traces")

    result = purge_expired(db_path, tmp_path / "traces", ttl_days=30, dry_run=True)

    assert result.dry_run is True
    assert result.expired_threads == 1
    assert result.checkpoints >= 1

    conn = sqlite3.connect(db_path)
    owners = {r[0] for r in conn.execute("SELECT thread_id FROM thread_owner")}
    checkpoints = {r[0] for r in conn.execute("SELECT DISTINCT thread_id FROM checkpoints")}
    conn.close()
    assert {"t-old", "t-new"} <= owners
    assert {"t-old", "t-new"} <= checkpoints


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


def test_expired_trace_files_are_removed(tmp_path) -> None:
    traces = tmp_path / "traces"
    traces.mkdir()
    old = traces / "20250101.jsonl"
    new = traces / "20261107.jsonl"
    old.write_text('{"node": "classify"}\n', encoding="utf-8")
    new.write_text('{"node": "respond"}\n', encoding="utf-8")
    old_ts = time.time() - 40 * 86400
    os.utime(old, (old_ts, old_ts))

    result = purge_expired(tmp_path / "state.db", traces, ttl_days=30)

    assert result.traces == 1
    assert not old.exists()
    assert new.exists()
