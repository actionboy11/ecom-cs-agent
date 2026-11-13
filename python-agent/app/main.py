"""FastAPI 入口。

启动时打开 SQLite checkpointer（会话状态落盘），进程退出释放连接。
CORS 现在放开的是本地开发来源；后续接 React 前端时改 ALLOWED_ORIGINS 即可。
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.graph.builder import build_graph, set_graph
from app.graph.checkpointer import sqlite_checkpointer
from app.session.retention import purge_expired
from app.session.thread_store import ThreadOwnerStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    store = await ThreadOwnerStore.open(settings.agent_state_db)
    app.state.thread_store = store

    # 启动时清理过期会话：默认 30 天；失败不应阻塞启动
    try:
        purged = await asyncio.to_thread(
            purge_expired, settings.agent_state_db, None, settings.session_ttl_days, False
        )
        logger.info("会话清理: %s", purged.as_dict())
    except Exception:
        logger.exception("会话清理失败，继续启动")

    async with sqlite_checkpointer(settings.agent_state_db) as checkpointer:
        set_graph(build_graph(checkpointer))
        try:
            yield
        finally:
            set_graph(None)
            app.state.thread_store = None
            await store.close()


app = FastAPI(
    title="cs-agent",
    description="电商售后客服 Agent（LangGraph + 多模型 + 业务系统工具）",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "cs-agent", "env": settings.app_env, "docs": "/docs"}
