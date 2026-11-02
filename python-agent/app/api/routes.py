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

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.graph.builder import get_graph
from app.observability.trace import trace_event
from app.tools import business_api

router = APIRouter(prefix="/api/v1", tags=["agent"])


class ChatRequest(BaseModel):
    thread_id: str = Field(description="会话 ID，同一会话传同一个值")
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


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


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
async def chat(req: ChatRequest) -> ChatResponse:
    graph = get_graph()
    trace_event(req.thread_id, "api", "chat_request", {"message": req.message[:200]})

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=req.message)],
            "thread_id": req.thread_id,
        },
        _config(req.thread_id),
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
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    graph = get_graph()

    async def gen() -> AsyncIterator[str]:
        try:
            async for chunk in graph.astream(
                {"messages": [HumanMessage(content=req.message)], "thread_id": req.thread_id},
                _config(req.thread_id),
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
async def resume(thread_id: str, req: ResumeRequest) -> ChatResponse:
    graph = get_graph()
    try:
        result = await graph.ainvoke(
            Command(resume={"approved": req.approved, "note": req.note}),
            _config(thread_id),
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
