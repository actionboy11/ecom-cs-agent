"""FastAPI 入口。

CORS 现在放开的是本地开发来源；后续接 React 前端时改 ALLOWED_ORIGINS 即可。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings

app = FastAPI(
    title="cs-agent",
    description="电商售后客服 Agent（LangGraph + 多模型 + 业务系统工具）",
    version="0.1.0",
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
