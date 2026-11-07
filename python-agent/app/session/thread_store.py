"""会话归属：`thread_owner` 表。

与 LangGraph 的 checkpointer 共用同一个 SQLite 文件（ADR-0002），
但用独立连接，避免与 checkpointer 的事务互相影响。
"""

from __future__ import annotations

import aiosqlite

from app.graph.checkpointer import resolve_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS thread_owner (
    thread_id  TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


class ThreadOwnerStore:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    @classmethod
    async def open(cls, db_path: str) -> "ThreadOwnerStore":
        path = resolve_db_path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(str(path))
        store = cls(conn)
        await conn.execute(_SCHEMA)
        await conn.commit()
        return store

    async def owner_of(self, thread_id: str) -> int | None:
        async with self._conn.execute(
            "SELECT user_id FROM thread_owner WHERE thread_id = ?", (thread_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return int(row[0]) if row else None

    async def bind(self, thread_id: str, user_id: int) -> None:
        """首次绑定；已存在则不改归属（防止抢占他人 thread）。"""
        await self._conn.execute(
            "INSERT OR IGNORE INTO thread_owner (thread_id, user_id) VALUES (?, ?)",
            (thread_id, user_id),
        )
        await self._conn.commit()

    async def touch(self, thread_id: str) -> None:
        await self._conn.execute(
            "UPDATE thread_owner SET updated_at = datetime('now') WHERE thread_id = ?",
            (thread_id,),
        )
        await self._conn.commit()

    async def close(self) -> None:
        await self._conn.close()
