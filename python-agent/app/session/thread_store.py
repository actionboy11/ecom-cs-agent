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
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    pending    INTEGER NOT NULL DEFAULT 0,
    pending_at TEXT
)
"""

# 老库升级：CREATE TABLE IF NOT EXISTS 不会补列
_MIGRATIONS = (
    "ALTER TABLE thread_owner ADD COLUMN pending INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE thread_owner ADD COLUMN pending_at TEXT",
    "CREATE INDEX IF NOT EXISTS idx_thread_pending ON thread_owner (pending, pending_at DESC)",
)


class ThreadOwnerStore:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    @classmethod
    async def open(cls, db_path: str) -> ThreadOwnerStore:
        path = resolve_db_path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(str(path))
        # 与 checkpointer 共用同一个库文件：WAL + 忙等待，避免并发写互相锁死
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        store = cls(conn)
        await conn.execute(_SCHEMA)
        for migration in _MIGRATIONS:
            try:
                await conn.execute(migration)
            except aiosqlite.OperationalError:
                # 列/索引已存在
                pass
        await conn.commit()
        return store

    async def owner_of(self, thread_id: str) -> int | None:
        async with self._conn.execute(
            "SELECT user_id FROM thread_owner WHERE thread_id = ?", (thread_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return int(row[0]) if row else None

    async def has_checkpoint(self, thread_id: str) -> bool:
        """该 thread 是否已有会话状态（可能有历史数据但缺少归属记录）。"""
        try:
            async with self._conn.execute(
                "SELECT 1 FROM checkpoints WHERE thread_id = ? LIMIT 1", (thread_id,)
            ) as cursor:
                return await cursor.fetchone() is not None
        except aiosqlite.OperationalError:
            # checkpoints 表尚未创建（全新库）＝没有历史状态
            return False

    async def bind(self, thread_id: str, user_id: int) -> bool:
        """首次绑定。返回是否由本次调用真正写入。

        并发下两个用户同时首聊同一个 thread 时，只有一方能 INSERT 成功；
        另一方拿到 False，调用方必须据此重新读归属并拒绝（避免 TOCTOU 抢占）。
        """
        cursor = await self._conn.execute(
            "INSERT INTO thread_owner (thread_id, user_id) VALUES (?, ?) "
            "ON CONFLICT(thread_id) DO NOTHING",
            (thread_id, user_id),
        )
        await self._conn.commit()
        return cursor.rowcount == 1

    async def touch(self, thread_id: str) -> None:
        # 毫秒精度：同一秒内的多次操作也能稳定排序
        await self._conn.execute(
            "UPDATE thread_owner SET updated_at = strftime('%Y-%m-%d %H:%M:%f','now') "
            "WHERE thread_id = ?",
            (thread_id,),
        )
        await self._conn.commit()

    async def mark_pending(self, thread_id: str) -> None:
        """挂起等人工：显式记 pending，避免被新会话挤出「最近 50」。"""
        await self._conn.execute(
            "UPDATE thread_owner SET pending = 1, "
            "pending_at = strftime('%Y-%m-%d %H:%M:%f','now') WHERE thread_id = ?",
            (thread_id,),
        )
        await self._conn.commit()

    async def clear_pending(self, thread_id: str) -> None:
        await self._conn.execute(
            "UPDATE thread_owner SET pending = 0, pending_at = NULL WHERE thread_id = ?",
            (thread_id,),
        )
        await self._conn.commit()

    async def list_pending(self, limit: int = 50) -> list[dict]:
        """待人工处理的会话（按挂起时间，最新在前）。"""
        async with self._conn.execute(
            "SELECT thread_id, user_id, updated_at, pending_at FROM thread_owner "
            "WHERE pending = 1 ORDER BY pending_at DESC, thread_id DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {
                "thread_id": r[0],
                "user_id": int(r[1]),
                "updated_at": r[2],
                "pending_at": r[3],
            }
            for r in rows
        ]

    async def list_recent(self, limit: int = 50) -> list[dict]:
        """最近活跃的会话（供调试/巡检；只返回元数据）。"""
        async with self._conn.execute(
            "SELECT thread_id, user_id, updated_at FROM thread_owner "
            "ORDER BY updated_at DESC, thread_id DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {"thread_id": r[0], "user_id": int(r[1]), "updated_at": r[2]} for r in rows
        ]

    async def close(self) -> None:
        await self._conn.close()
