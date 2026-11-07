"""SQLite checkpointer：会话状态落盘，进程重启后可继续。

与业务数据分开存（ADR-0002）：会话是「可丢状态」，订单/售后是「不可丢事实」。
相对路径统一解析到仓库根，避免从不同目录启动时写出第二个库。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

logger = logging.getLogger(__name__)

# checkpointer.py -> graph -> app -> python-agent -> 仓库根
REPO_ROOT = Path(__file__).resolve().parents[3]


def resolve_db_path(db_path: str) -> Path:
    path = Path(db_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


@asynccontextmanager
async def sqlite_checkpointer(db_path: str) -> AsyncIterator[AsyncSqliteSaver]:
    """打开（必要时创建）SQLite 状态库。

    生命周期与 FastAPI 进程一致：进程退出即释放连接；
    数据留在文件里，重启后从同一个库恢复。
    """
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("会话状态库: %s", path)
    async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
        yield saver
