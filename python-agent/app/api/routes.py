"""对外 HTTP 接口（API-first）。

前端后续用 React/TS 接入时，只需要消费这里的三组接口：
- POST /api/v1/chat          一次性返回
- POST /api/v1/chat/stream   SSE 流式（展示 Agent 过程）
- POST /api/v1/threads/{id}/resume  人工审核后恢复
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.graph.builder import get_graph
from app.observability.trace import trace_event
from app.security.auth import CurrentUser, require_user
from app.session.thread_store import ThreadOwnerStore
from app.tools import audit_client, business_api

router = APIRouter(prefix="/api/v1", tags=["agent"])


def get_thread_store(request: Request) -> ThreadOwnerStore:
    store = getattr(request.app.state, "thread_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="服务未就绪")
    return store


async def _deny(thread_id: str, user: CurrentUser, reason: str, path: str = "") -> None:
    """越权与不存在统一 404，并留下 DENIED 轨迹（trace + MySQL 审计）。"""
    trace_event(thread_id, "auth", "denied", {"user": user.username, "role": user.role, "reason": reason})
    await audit_client.record_thread_denied(
        actor=user.username,
        role=user.role,
        thread_id=thread_id,
        path=path or "/api/v1/chat",
        reason=reason,
    )
    raise HTTPException(status_code=404, detail="会话不存在")


async def _ensure_thread_access(
    store: ThreadOwnerStore,
    thread_id: str,
    user: CurrentUser,
    *,
    bind_if_new: bool,
    allow_agent: bool,
    path: str = "",
) -> None:
    """会话归属校验：不存在与不属于当前用户统一 404（ADR-0001）。"""
    owner = await store.owner_of(thread_id)
    if owner is None:
        if not bind_if_new:
            await _deny(thread_id, user, "resume_unknown", path)
        # 历史遗留：checkpointer 里有状态但没有归属记录（#13 之前的会话）。
        # 这种 thread 一律拒绝，避免任何人凭 thread_id 直接接管历史对话。
        if await store.has_checkpoint(thread_id):
            await _deny(thread_id, user, "legacy_unowned", path)
        if not await store.bind(thread_id, user.user_id):
            # 并发首聊：另一方先绑定成功，此时必须按归属重新判定，不能继续
            owner = await store.owner_of(thread_id)
            if owner != user.user_id:
                await _deny(thread_id, user, "bind_race", path)
        return
    if owner != user.user_id and not (allow_agent and user.is_agent):
        await _deny(thread_id, user, "not_owner", path)
    await store.touch(thread_id)


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1, description="会话 ID，同一会话传同一个值")
    message: str = Field(min_length=1, description="用户输入")
    user_id: str | None = Field(default=None, description="用户 ID（W2 用于长期记忆）")


class ChatResponse(BaseModel):
    thread_id: str
    reply: str
    intent: str | None = None
    order_no: str | None = None
    tool_result: dict[str, Any] | None = None
    needs_human: bool = False
    interrupt: dict[str, Any] | None = None


class ResumeRequest(BaseModel):
    approved: bool = Field(description="人工是否同意转接/通过")
    note: str | None = None


def _config(thread_id: str, token: str = "") -> dict[str, Any]:
    """会话配置：auth_token 只走 config，不进 state，避免被 checkpointer 落盘。"""
    return {"configurable": {"thread_id": thread_id, "auth_token": token}}


def _extract_interrupt(result: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__") or ()
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", None)
    return value if isinstance(value, dict) else {"value": value}


@router.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "business_api": await business_api.healthy(),
        "ts": int(time.time()),
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: CurrentUser = Depends(require_user),
    store: ThreadOwnerStore = Depends(get_thread_store),
) -> ChatResponse:
    await _ensure_thread_access(
        store, req.thread_id, user, bind_if_new=True, allow_agent=False, path="/api/v1/chat"
    )
    graph = get_graph()
    trace_event(req.thread_id, "api", "chat_request", {"message": req.message[:200]})

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=req.message)],
            "thread_id": req.thread_id,
        },
        _config(req.thread_id, user.token),
    )
    interrupt = _extract_interrupt(result)
    return ChatResponse(
        thread_id=req.thread_id,
        reply=result.get("reply", ""),
        intent=result.get("intent"),
        order_no=result.get("order_no"),
        tool_result=result.get("tool_result"),
        needs_human=interrupt is not None,
        interrupt=interrupt,
    )


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user: CurrentUser = Depends(require_user),
    store: ThreadOwnerStore = Depends(get_thread_store),
) -> StreamingResponse:
    await _ensure_thread_access(
        store, req.thread_id, user, bind_if_new=True, allow_agent=False, path="/api/v1/chat/stream"
    )
    graph = get_graph()

    async def gen() -> AsyncIterator[str]:
        try:
            async for chunk in graph.astream(
                {"messages": [HumanMessage(content=req.message)], "thread_id": req.thread_id},
                _config(req.thread_id, user.token),
                stream_mode="updates",
            ):
                for node, update in chunk.items():
                    payload = json.dumps(
                        {"node": node, "update": update},
                        ensure_ascii=False,
                        default=str,
                    )
                    yield f"event: node\ndata: {payload}\n\n"
            yield "event: end\ndata: {}\n\n"
        except Exception as exc:  # noqa: BLE001 - 流式接口必须把错误发给前端
            yield f"event: error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/threads/{thread_id}/resume", response_model=ChatResponse)
async def resume(
    thread_id: str,
    req: ResumeRequest,
    user: CurrentUser = Depends(require_user),
    store: ThreadOwnerStore = Depends(get_thread_store),
) -> ChatResponse:
    # 坐席审批恢复不受归属限制；买家只能恢复自己的会话
    await _ensure_thread_access(
        store, thread_id, user, bind_if_new=False, allow_agent=True,
        path=f"/api/v1/threads/{thread_id}/resume",
    )
    graph = get_graph()
    try:
        result = await graph.ainvoke(
            Command(resume={"approved": req.approved, "note": req.note}),
            _config(thread_id, user.token),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=409, detail=f"该会话当前没有待处理的人工任务: {exc}") from exc

    interrupt = _extract_interrupt(result)
    return ChatResponse(
        thread_id=thread_id,
        reply=result.get("reply", ""),
        intent=result.get("intent"),
        order_no=result.get("order_no"),
        tool_result=result.get("tool_result"),
        needs_human=interrupt is not None,
        interrupt=interrupt,
    )
