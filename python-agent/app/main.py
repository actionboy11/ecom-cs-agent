"""FastAPI 入口。

启动时打开 SQLite checkpointer（会话状态落盘），进程退出释放连接。
CORS 现在放开的是本地开发来源；后续接 React 前端时改 ALLOWED_ORIGINS 即可。
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.graph.builder import build_graph, set_graph
from app.graph.checkpointer import sqlite_checkpointer


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with sqlite_checkpointer(settings.agent_state_db) as checkpointer:
        set_graph(build_graph(checkpointer))
        try:
            yield
        finally:
            set_graph(None)


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
