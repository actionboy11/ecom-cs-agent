"""SQLite checkpointer：会话状态落盘，进程重启后可继续。

与业务数据分开存（ADR-0002）：会话是「可丢状态」，订单/售后是「不可丢事实」。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


@asynccontextmanager
async def sqlite_checkpointer(db_path: str) -> AsyncIterator[AsyncSqliteSaver]:
    """打开（必要时创建）SQLite 状态库。

    生命周期与 FastAPI 进程一致：进程退出即释放连接；
    数据留在文件里，重启后从同一个库恢复。
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
        yield saver
