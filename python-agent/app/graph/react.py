"""ReAct 主循环（MVP）：LLM 自主选读工具、传参、看结果重试；写操作后续接入。"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app.graph.state import AgentState
from app.graph.time_refs import TZ, parse_time_reference
from app.knowledge import store as knowledge_store
from app.llm.registry import get_chat_model
from app.tools import business_api

MAX_STEPS = 6
ACTIVE_ORDER_TTL = timedelta(minutes=30)


class FindOrdersArgs(BaseModel):
    product_terms: list[str] = Field(default_factory=list, description="商品词，如 鞋、耳机")
    created_from: str | None = Field(default=None, description="下单日期下限 yyyy-MM-dd")
    created_to: str | None = Field(default=None, description="下单日期上限 yyyy-MM-dd")
    delivered_from: str | None = Field(default=None, description="签收日期下限 yyyy-MM-dd")
    delivered_to: str | None = Field(default=None, description="签收日期上限 yyyy-MM-dd")
    action: str | None = Field(default=None, description="refund/return/exchange/logistics/query")
    limit: int = Field(default=5, ge=1, le=10)


class OrderArgs(BaseModel):
    order_no: str = Field(description="订单号，例如 CS2024001")


class SkuArgs(BaseModel):
    sku: str = Field(description="SKU，例如 SKU1001")


class PolicyArgs(BaseModel):
    query: str = Field(description="政策问题，如 拆封还能退吗")


class AfterSalesArgs(BaseModel):
    order_no: str = Field(description="订单号")
    reason: str = Field(description="原因")


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _build_tools(token: str) -> list[StructuredTool]:
    async def find_orders(**kwargs: Any) -> str:
        rows = await business_api.find_my_orders(token, **kwargs)
        return _json({"candidates": rows, "count": len(rows)})

    async def query_order(order_no: str) -> str:
        return _json(await business_api.get_order(order_no, token))

    async def query_logistics(order_no: str) -> str:
        return _json(await business_api.get_logistics(order_no, token))

    async def get_product(sku: str) -> str:
        return _json(await business_api.get_product(sku, token))

    async def search_policy(query: str) -> str:
        result = await asyncio.to_thread(knowledge_store.retrieve, query)
        return _json({"knowledge": result.knowledge, "policy_refs": result.policy_refs})

    async def create_after_sales(order_no: str, reason: str) -> str:
        # 真正执行在 ReAct 循环里，先经过 interrupt 确认；这个函数不会被直接调用
        return _json({"status": "pending_confirmation", "order_no": order_no, "reason": reason})

    return [
        StructuredTool.from_function(
            coroutine=create_after_sales,
            name="create_refund",
            description="发起退款申请；会触发用户逐次确认，确认后才会真正提交。",
            args_schema=AfterSalesArgs,
        ),
        StructuredTool.from_function(
            coroutine=create_after_sales,
            name="create_return",
            description="发起退货申请；会触发用户逐次确认，确认后才会真正提交。",
            args_schema=AfterSalesArgs,
        ),
        StructuredTool.from_function(
            coroutine=create_after_sales,
            name="create_exchange",
            description="发起换货申请；会触发用户逐次确认，确认后才会真正提交。",
            args_schema=AfterSalesArgs,
        ),
        StructuredTool.from_function(
            coroutine=find_orders,
            name="find_my_orders",
            description="按商品/时间/状态召回当前用户订单，返回带 score 与 reasons 的候选。用户只描述商品时先用它。",
            args_schema=FindOrdersArgs,
        ),
        StructuredTool.from_function(
            coroutine=query_order,
            name="query_order",
            description="按订单号查订单详情；仅本人订单。",
            args_schema=OrderArgs,
        ),
        StructuredTool.from_function(
            coroutine=query_logistics,
            name="query_logistics",
            description="按订单号查物流轨迹；仅本人订单。",
            args_schema=OrderArgs,
        ),
        StructuredTool.from_function(
            coroutine=get_product,
            name="get_product",
            description="按 SKU 查商品参数与库存。",
            args_schema=SkuArgs,
        ),
        StructuredTool.from_function(
            coroutine=search_policy,
            name="search_policy",
            description="检索售后政策条款，返回 knowledge 与 policy_refs。",
            args_schema=PolicyArgs,
        ),
    ]


def _active_order(state: AgentState) -> str | None:
    order_no = state.get("active_order_no")
    stamped = state.get("active_order_at")
    if not order_no or not stamped:
        return None
    try:
        stamp = datetime.fromisoformat(str(stamped))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    if datetime.now(UTC) - stamp > ACTIVE_ORDER_TTL:
        return None
    return str(order_no)


async def react_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    token = (config or {}).get("configurable", {}).get("auth_token") or ""
    if not token:
        return _fallback([], "unauthorized", None, None)

    tools = _build_tools(token)
    tool_map = {tool.name: tool for tool in tools}
    active = _active_order(state)
    last_text = str(state["messages"][-1].content) if state.get("messages") else ""
    hint = parse_time_reference(last_text)
    today = datetime.now(TZ).date().isoformat()
    time_line = f"当前日期（Asia/Shanghai）：{today}。"
    if hint:
        time_line += (
            f"系统已把用户时间解析为绝对区间：{hint['field']}_from={hint['from']}，"
            f"{hint['field']}_to={hint['to']}；调用 find_my_orders 时必须使用这组日期。"
        )

    system = SystemMessage(
        content=(
            "你是电商售后 Agent，用户已登录。"
            "必须调用工具获取事实，可多次调用、换工具、重试；不要编造订单或政策。"
            "用户只描述商品（我的鞋/那个耳机）时先 find_my_orders；有明确订单号再用 query_order/query_logistics。"
            "政策问题用 search_policy，并保留 [Pxx] 引用。"
            "商品价格/库存先 find_my_orders 拿 sku，再 get_product 查参数；不要凭记忆报价。"
            "候选订单有多个时，列出前 3 个让用户选，不要猜。"
            f"当前会话订单：{active or '无'}。"
            "如果用户回复「选择订单 CSxxxx」，直接用该订单继续，不要再让用户选。"
            f"用户说退/退款且订单已确定时调 create_refund；说退货调 create_return；说换货调 create_exchange。"
            "不要只用文字询问，确认由系统卡片完成；工具返回成功结果后明确说已提交，不要再让用户确认。"
            "示例：用户说『我要退货』→ create_return；『我要换货』→ create_exchange；『我要退款/退钱』→ create_refund。"
            "即使工具返回政策，只要用户明确要求办理且订单号确定，也必须调用对应写工具。"
            f"{time_line}"
            f"最多 {MAX_STEPS} 步；工具连续失败或无法确认时转人工。"
        )
    )
    messages: list[BaseMessage] = [system, *state["messages"][-8:]]
    trace: list[dict[str, Any]] = []
    active_order = active
    active_at = state.get("active_order_at")
    fallback_reason: str | None = None
    failures = 0

    llm = get_chat_model("reasoning", temperature=0).bind_tools(tools)
    for step in range(MAX_STEPS):
        try:
            ai: AIMessage = await llm.ainvoke(messages)
        except Exception as exc:  # noqa: BLE001 - 模型失败回退旧链路
            trace.append({"step": step, "error": str(exc)[:160]})
            fallback_reason = "model_error"
            break

        if not ai.tool_calls:
            text = str(ai.content).strip()
            if not text:
                fallback_reason = "empty_reply"
                break
            return {
                "reply": text,
                "messages": [AIMessage(content=text)],
                "reply_chain": "react",
                "tool_trace": trace,
                "react_fallback": False,
                "react_fallback_reason": None,
                "active_order_no": active_order,
                "active_order_at": active_at,
            }

        messages.append(ai)
        for call in ai.tool_calls:
            name = call.get("name", "")
            args = call.get("args", {}) or {}
            call_id = call.get("id", f"call-{step}-{name}")
            write_types = {"create_refund": "REFUND", "create_return": "RETURN", "create_exchange": "EXCHANGE"}
            if name in write_types:
                as_type = write_types[name]
                if as_type == "REFUND" and "退货" in last_text:
                    as_type = "RETURN"
                elif as_type == "REFUND" and "换货" in last_text:
                    as_type = "EXCHANGE"
                order_no = str(args.get("order_no", ""))
                reason = str(args.get("reason", ""))
                try:
                    order = await business_api.get_order(order_no, token)
                except Exception:  # noqa: BLE001 - 写校验失败直接降级
                    fallback_reason = "write_validation_failed"
                    break
                trace.append({"step": step, "tool": name, "args": args, "result": "等待用户确认"})
                decision = interrupt(
                    {
                        "type": "write_approval",
                        "action": as_type.lower(),
                        "order_no": order_no,
                        "reason": reason,
                        "order": order,
                    }
                )
                approved = bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision)
                if not approved:
                    trace.append({"step": step, "tool": name, "args": args, "result": "用户取消"})
                    messages.append(ToolMessage(content=_json({"status": "cancelled"}),
                                                tool_call_id=call_id))
                    continue
                try:
                    data = await business_api.apply_after_sales(order_no, as_type, reason, token)
                    trace.append({"step": step, "tool": name, "args": args, "result": str(data)[:300]})
                    messages.append(ToolMessage(content=_json(data), tool_call_id=call_id))
                    active_order = order_no
                    active_at = datetime.now(UTC).isoformat()
                except Exception as exc:  # noqa: BLE001
                    trace.append({"step": step, "tool": name, "args": args, "error": str(exc)[:200]})
                    messages.append(ToolMessage(content=_json({"error": str(exc)[:200]}),
                                                tool_call_id=call_id))
                continue

            tool = tool_map.get(name)
            if tool is None:
                messages.append(ToolMessage(content=_json({"error": f"未知工具 {name}"}),
                                            tool_call_id=call_id))
                continue
            try:
                result = await tool.ainvoke(args)
                trace.append({
                    "step": step,
                    "tool": name,
                    "args": args,
                    "result": str(result) if name == "find_my_orders" else str(result)[:300],
                })
                messages.append(ToolMessage(content=str(result), tool_call_id=call_id))
                failures = 0
                order_no = args.get("order_no")
                if order_no and name in ("query_order", "query_logistics"):
                    active_order = str(order_no)
                    active_at = datetime.now(UTC).isoformat()
                if name == "find_my_orders":
                    try:
                        payload = json.loads(str(result))
                        if not payload.get("candidates"):
                            fallback_reason = "no_candidates"
                            break
                    except (TypeError, ValueError):
                        pass
            except Exception as exc:  # noqa: BLE001 - 工具失败交给模型换工具/重试
                failures += 1
                trace.append({"step": step, "tool": name, "args": args, "error": str(exc)[:200]})
                messages.append(ToolMessage(content=_json({"error": str(exc)[:200]}),
                                            tool_call_id=call_id))
                if failures >= 2:
                    fallback_reason = "tool_failure"
                    break

        if fallback_reason:
            break

    if fallback_reason is None:
        fallback_reason = "step_limit"
    return _fallback(trace, fallback_reason, active_order, active_at)


def _fallback(trace: list[dict[str, Any]], reason: str, active_order: str | None,
              active_at: str | None) -> dict[str, Any]:
    return {
        "react_fallback": True,
        "react_fallback_reason": reason,
        "tool_trace": trace,
        "reply_chain": "",
        "active_order_no": active_order,
        "active_order_at": active_at,
    }


def route_after_react(state: AgentState) -> str:
    return "tools" if state.get("react_fallback") else "end"
