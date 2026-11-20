"""ReAct 主循环（MVP）：LLM 自主选读工具、传参、看结果重试；写操作后续接入。"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphInterrupt
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app import clock, skill_registry
from app.graph.preflight import run_preflight
from app.graph.query_context import ALL_ACTIONS, build_context, resolve_candidate
from app.graph.state import AgentState
from app.graph.time_refs import parse_time_reference
from app.knowledge import store as knowledge_store
from app.llm.registry import get_chat_model
from app.tools import business_api

ORDER_RE = re.compile(r"(CS\d{7,})", re.IGNORECASE)
SELECT_RE = re.compile(r"选择订单\s*(CS\d{7,})", re.IGNORECASE)
SELECT_RE = re.compile(r"选择订单\s*(CS\d{7,})", re.IGNORECASE)
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


class LoadSkillArgs(BaseModel):
    name: str = Field(description="skill 名称，例如 order-lookup / normal-return / custom-return")


class HandoffArgs(BaseModel):
    reason: str = Field(description="转人工原因")
    summary: str = Field(default="", description="给坐席的摘要")


class PrepareUserActionArgs(BaseModel):
    action: str = Field(description="change_address / invoice / return / exchange")
    order_no: str = Field(description="已识别的订单号")
    quality: bool = Field(default=False, description="8–15 天质量问题退货/换货时传 true")


class InterceptArgs(BaseModel):
    order_no: str = Field(description="运输中的订单号")


class QueryAfterSalesArgs(BaseModel):
    order_no: str | None = Field(default=None, description="订单号；为空则查当前用户全部售后")


class UrgeArgs(BaseModel):
    order_no: str = Field(description="订单号")
    reason: str = Field(default="用户申请催件", description="催件原因")


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _build_tools(token: str, thread_id: str) -> list[StructuredTool]:
    async def find_orders(**kwargs: Any) -> str:
        rows = await business_api.find_my_orders(token, **kwargs)
        return _json({"candidates": rows, "count": len(rows)})

    async def query_order(order_no: str) -> str:
        return _json(await business_api.get_order(order_no, token))

    async def query_logistics(order_no: str) -> str:
        return _json(await business_api.get_logistics(order_no, token))

    async def get_product(sku: str) -> str:
        return _json(await business_api.get_product(sku, token))

    async def query_after_sales(order_no: str | None = None) -> str:
        rows = await business_api.list_after_sales(token)
        if order_no:
            rows = [row for row in rows if row.get("orderNo") == order_no]
        return _json({"after_sales": rows, "count": len(rows)})

    async def prepare_user_action(action: str, order_no: str, quality: bool = False) -> str:
        order = await business_api.get_order(order_no, token)
        eligibility_action = "address" if action == "change_address" else action
        eligibility = await business_api.order_eligibility(
            order_no, eligibility_action, token, quality=quality
        )
        if not eligibility.get("allowed"):
            return _json({"error": eligibility.get("reason"), "eligibility": eligibility})
        fields = {
            "change_address": ["receiver", "phone", "address"],
            "invoice": ["title", "taxId", "email"],
            "return": ["reason", "evidence"],
            "exchange": ["reason", "evidence", "target"],
        }.get(action, [])
        return _json({
            "type": "user_action",
            "action": action,
            "order_no": order_no,
            "order_summary": f"{order.get('item')}，{order.get('status')}",
            "message": {
                "change_address": "请填写新地址",
                "invoice": "请填写发票信息",
                "return": "请填写退货原因" + ("和凭证" if eligibility.get("requiresEvidence") else ""),
                "exchange": "请填写换货原因和目标规格",
            }.get(action, "请填写信息"),
            "fields": fields,
            "after_sales_type": {"return": "RETURN", "exchange": "EXCHANGE"}.get(action),
            "shipping_payer": eligibility.get("shippingPayer"),
            "requires_evidence": eligibility.get("requiresEvidence", False),
        })

    async def intercept_order(order_no: str) -> str:
        return _json(await business_api.intercept_logistics(order_no, token))

    async def urge_logistics(order_no: str, reason: str = "用户申请催件") -> str:
        return _json(await business_api.urge_logistics(order_no, token, reason))

    async def search_policy(query: str) -> str:
        result = await asyncio.to_thread(knowledge_store.retrieve, query)
        return _json({"knowledge": result.knowledge, "policy_refs": result.policy_refs})

    async def load_skill(name: str) -> str:
        try:
            return skill_registry.load(name)
        except ValueError as exc:
            return _json({"error": str(exc)})

    async def handoff_to_human(reason: str, summary: str = "") -> str:
        decision = interrupt(
            {
                "type": "human_handoff",
                "thread_id": thread_id,
                "reason": reason,
                "summary": summary,
            }
        )
        approved = bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision)
        return _json({"status": "resumed", "approved": approved})

    async def create_after_sales(order_no: str, reason: str) -> str:
        # 真正执行在 ReAct 循环里，先经过 interrupt 确认；这个函数不会被直接调用
        return _json({"status": "pending_confirmation", "order_no": order_no, "reason": reason})

    return [
        StructuredTool.from_function(
            coroutine=load_skill,
            name="load_skill",
            description="按名称加载 SKILL.md 全文；需要走订单定位/正常退货/定制退货时先调用它。",
            args_schema=LoadSkillArgs,
        ),
        StructuredTool.from_function(
            coroutine=handoff_to_human,
            name="handoff_to_human",
            description="解释完政策后转人工；会挂起等坐席恢复。定制无质量问题、超期等使用。",
            args_schema=HandoffArgs,
        ),
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
            coroutine=query_after_sales,
            name="query_after_sales",
            description="查售后进度/换货补发/退款审核；先 query_order 再查售后，按 order_no 过滤。",
            args_schema=QueryAfterSalesArgs,
        ),
        StructuredTool.from_function(
            coroutine=prepare_user_action,
            name="prepare_user_action",
            description="订单已识别后，为改地址/发票准备前端表单；必须先定位订单再调用。",
            args_schema=PrepareUserActionArgs,
        ),
        StructuredTool.from_function(
            coroutine=intercept_order,
            name="intercept_order",
            description="运输中退款前拦截快递；返回 INTERCEPTED/FAILED。失败必须转人工。",
            args_schema=InterceptArgs,
        ),
        StructuredTool.from_function(
            coroutine=urge_logistics,
            name="urge_logistics",
            description="对订单发起催件，创建 URGE 售后请求；用户要求催件时直接调用，不需要确认。",
            args_schema=UrgeArgs,
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


def _candidate_selection(text: str, candidates: list[dict[str, Any]]) -> str | None:
    return resolve_candidate(text, candidates)


QUALITY_HINTS = ("质量", "坏", "破", "漏", "杂音", "故障", "开线", "发错", "错色", "差", "磕", "异响", "充不进", "不工作", "不匹配")


async def _action_eligible(token: str, order_no: str | None, action: str, text: str) -> bool:
    """Guard 只在订单可办、无已有售后、政策不冲突时推动写操作。"""
    if not order_no:
        return False
    try:
        order = await business_api.get_order(order_no, token)
        existing = await business_api.list_after_sales(token)
    except Exception:  # noqa: BLE001
        return False
    if any(row.get("orderNo") == order_no for row in existing):
        return False
    status = str(order.get("status") or "")
    tags = {item.strip() for item in str(order.get("tags") or "").split(",") if item.strip()}
    if action == "urge":
        return status in ("待发货", "运输中", "已发货")
    if action == "refund":
        return status in ("待发货", "运输中", "已发货")
    if action not in ("return", "exchange"):
        return False
    if status != "已签收":
        return False
    delivered = order.get("deliveredAt")
    if not delivered:
        return False
    try:
        days = (clock.today() - datetime.fromisoformat(str(delivered)).date()).days
    except ValueError:
        return False
    if days > 15:
        return False
    if "custom" in tags and not any(word in text for word in QUALITY_HINTS):
        return False
    return "gift" not in tags


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
    if clock.now(UTC) - stamp > ACTIVE_ORDER_TTL:
        return None
    return str(order_no)



SAFETY_HANDOFF_HINTS = ("鼓包", "冒烟", "起火", "爆炸", "漏电", "发烫", "烫手")
POLICY_HANDOFF_HINTS = ("赔偿", "赔我", "赔钱", "凭什么", "拒了", "拒绝")


def _force_handoff_for_policy(text: str, thread_id: str) -> None:
    """安全/赔付/争议不是普通售后，直接转人工挂起。"""
    safety = any(word in text for word in SAFETY_HANDOFF_HINTS)
    dispute = any(word in text for word in POLICY_HANDOFF_HINTS) or (
        "留着" in text and "退" in text
    )
    if not (safety or dispute):
        return
    decision = interrupt(
        {
            "type": "human_handoff",
            "thread_id": thread_id,
            "reason": "safety_escalation" if safety else "policy_dispute",
            "summary": text,
        }
    )
    if isinstance(decision, dict) and decision.get("approved") is False:
        return


async def _force_handoff_if_ineligible(
    token: str, order_no: str | None, action: str | None, text: str, reply: str, thread_id: str
) -> None:
    """资格明确返回 HANDOFF 时，真正挂起，而不是只让模型解释。"""
    if not order_no:
        # 模型已在回复里锁定唯一订单时，用该订单做资格复核
        found = set(re.findall(r"CS\d{7,}", reply, re.IGNORECASE))
        if len(found) == 1:
            order_no = next(iter(found))
    if not order_no:
        return
    if action not in ALL_ACTIONS:
        if "换" in text:
            action = "exchange"
        elif "退" in text:
            action = "return" if "退货" in text else "refund"
        else:
            return
    quality = any(word in text for word in QUALITY_HINTS)
    try:
        eligibility = await business_api.order_eligibility(order_no, action, token, quality=quality)
    except Exception:  # noqa: BLE001
        return
    if eligibility.get("allowed") or str(eligibility.get("nextAction")) != "HANDOFF":
        return
    decision = interrupt(
        {
            "type": "human_handoff",
            "thread_id": thread_id,
            "reason": eligibility.get("reasonCode") or "ELIGIBILITY_HANDOFF",
            "summary": f"{text}；{eligibility.get('reason') or ''}".strip("；"),
            "order_no": order_no,
        }
    )
    if isinstance(decision, dict) and decision.get("approved") is False:
        return

async def _fallback_user_action(
    token: str, order_no: str | None, intent: str | None, text: str, reply: str
) -> dict[str, Any] | None:
    """模型没调 prepare 时，资格允许就直接生成表单，避免“只解释不办事”。"""
    if not order_no:
        found = set(re.findall(r"CS\d{7,}", reply, re.IGNORECASE))
        if len(found) == 1:
            order_no = next(iter(found))
    if not order_no:
        return None
    if intent not in ("refund", "return", "exchange") and "退" not in text and "换" not in text:
        return None
    action = "exchange" if (intent == "exchange" or "换" in text) else "return"
    quality = any(word in text for word in QUALITY_HINTS)
    try:
        eligibility = await business_api.order_eligibility(order_no, action, token, quality=quality)
        order = await business_api.get_order(order_no, token)
    except Exception:  # noqa: BLE001
        return None
    next_action = str(eligibility.get("nextAction") or "")
    if not eligibility.get("allowed") or next_action not in ("RETURN_FORM", "EXCHANGE_FORM"):
        return None
    fields = ["reason", "evidence"] + (["target"] if action == "exchange" else [])
    return {
        "type": "user_action",
        "action": action,
        "order_no": order_no,
        "order_summary": f"{order.get('item')}，{order.get('status')}",
        "message": "请填写退货原因" if action == "return" else "请填写换货原因和目标规格",
        "fields": fields,
        "after_sales_type": "RETURN" if action == "return" else "EXCHANGE",
        "shipping_payer": eligibility.get("shippingPayer"),
        "requires_evidence": eligibility.get("requiresEvidence", False),
    }


async def react_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    token = (config or {}).get("configurable", {}).get("auth_token") or ""
    if not token:
        return _fallback([], "unauthorized", None, None)

    thread_id = state.get("thread_id", "unknown")
    tools = _build_tools(token, thread_id)
    tool_map = {tool.name: tool for tool in tools}
    active = _active_order(state)
    last_text = str(state["messages"][-1].content) if state.get("messages") else ""
    active_at = state.get("active_order_at")
    context = build_context(last_text, state)
    candidates = context.candidates
    pending_action = state.get("pending_write_action")
    pending_user_action = state.get("pending_user_action")
    ui_action: dict[str, Any] | None = None
    if active is None and state.get("active_order_no"):
        active_at = None
    if context.selected_order:
        active = context.selected_order
        active_at = clock.now(UTC).isoformat()
    elif context.order_no:
        active = context.order_no
        active_at = clock.now(UTC).isoformat()
    elif any(word in last_text for word in ("不是这单", "不是这个", "都不是", "换一个", "不对")):
        active = None
        active_at = None
    hint = parse_time_reference(last_text)
    today = clock.today().isoformat()
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
            "售后进度/退款到账先 query_order，再 query_after_sales；物流问题按 find_my_orders → query_order → query_logistics；催件必须调 urge_logistics，不要只回复。"
            "用户只描述商品（我的鞋/那个耳机）时先 find_my_orders；有明确订单号再用 query_order/query_logistics。"
            "没有订单号时禁止直接回答‘查不到’，必须先 find_my_orders 查候选。"
            "政策问题用 search_policy，并保留 [Pxx] 引用。"
            "商品价格/库存先 find_my_orders 拿 sku，再 get_product 查参数；不要凭记忆报价。"
            "订单 tags：gift 表示赠品（无明确条款时转人工），custom 表示定制（不适用七天无理由）。"
            "候选订单有多个时，列出前 3 个让用户选，不要猜。"
            "find_my_orders 只返回一个候选且用户明确要退/换时，直接调用对应写工具，不要再问‘是这单吗’，系统确认卡负责确认。"
            f"已识别商品：{'、'.join(state.get('matched_products') or []) or '无'}；有商品时优先用 canonical 作为 product_terms。"
            + (context.prompt() + "\n" if context.prompt() else "")
            + (
                f"上一轮待办：{pending_action}。用户本轮已选订单 {active} 时，直接调用对应写工具，不要再问。"
                if pending_action and active else ""
            )
            + (
                f"待办能力动作：{pending_user_action.get('action')}。必须先定位订单；订单确定后调用 prepare_user_action，不要直接让用户填订单号，也不要直接给表单。"
                if pending_user_action else ""
            )
            + f"当前会话订单：{active or '无'}。"
            "如果用户回复「选择订单 CSxxxx」，直接用该订单继续，不要再让用户选。"
            f"用户说退/退款且订单已确定、未签收或政策允许仅退款时调 create_refund；说退货调 create_return；说换货调 create_exchange。"
            "用户说退款/退钱，但订单已签收且政策要求退货退款时，先说明‘需要寄回商品才能退款’，并询问是否接受退货退款；不要直接调 create_refund 或 create_return。"
            "不要只用文字询问，确认由系统卡片完成；工具返回成功结果后明确说已提交，不要再让用户确认。"
            f"可用 Skill（先用 load_skill(name) 读取全文，再严格按文档步骤执行）：\n{skill_registry.descriptions()}"
            "没有订单号时先 load_skill('order-lookup')；退货先 load_skill('normal-return') 或 load_skill('custom-return')。"
            "Skill 文档要求 handoff 时，先用一句话解释政策，再调 handoff_to_human。"
            "示例：用户说『我要退货』→ 先判 tags；『我要换货』→ create_exchange；『未发货，我要退款』→ create_refund；『已签收，我要退款』→ 先判断政策是否要求退货，冲突时先澄清。"
            "即使工具返回政策，只要用户明确要求办理且订单号确定，也必须调用对应写工具。"
            f"{time_line}"
            f"最多 {MAX_STEPS} 步；工具连续失败或无法确认时转人工。"
        )
    )
    messages: list[BaseMessage] = [system, *state["messages"][-8:]]
    trace: list[dict[str, Any]] = []
    active_order = active
    fallback_reason: str | None = None

    selected = SELECT_RE.search(last_text)
    if selected:
        active_order = selected.group(1).upper()
        active_at = clock.now(UTC).isoformat()
    preflight = await run_preflight(last_text, state, token, context.order_no or active_order)
    if preflight.trace:
        trace.extend(preflight.trace)
    if preflight.order_no:
        active_order = preflight.order_no
        active_at = clock.now(UTC).isoformat()
    if preflight.candidates:
        candidates = preflight.candidates[:5]
    if preflight.facts:
        messages.append(SystemMessage(content="已预取：" + "；".join(preflight.facts)))
    if preflight.intercept_failed:
        decision = interrupt(
            {
                "type": "human_handoff",
                "thread_id": thread_id,
                "reason": "INTERCEPT_FAILED",
                "summary": "运输中订单拦截失败，无法确认退款",
                "order_no": preflight.order_no,
            }
        )
        if isinstance(decision, dict) and decision.get("approved") is False:
            return _fallback(trace, "handoff_rejected", active_order, active_at)
    failures = 0
    guard_retried = False

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
            if (
                pending_user_action
                and active
                and not any(item.get("tool") == "prepare_user_action" for item in trace)
                and not guard_retried
            ):
                guard_retried = True
                messages.append(SystemMessage(content=(
                    f"用户要做 {pending_user_action.get('action')}，订单已确定为 {active}。"
                    "现在必须调用 prepare_user_action，不要直接给表单或让用户填订单号。"
                )))
                continue
            required_action = context.action if context.action in ALL_ACTIONS else pending_action
            required_tools = {
                "refund": "create_refund", "return": "create_return",
                "exchange": "create_exchange", "urge": "urge_logistics",
            }
            if (
                required_action in required_tools
                and (active_order or active)
                and not any(item.get("tool") == required_tools[required_action] for item in trace)
                and not guard_retried
                and await _action_eligible(token, active_order or active, required_action, last_text)
            ):
                action_tool = required_tools[required_action]
                if required_action in ("return", "exchange"):
                    action_tool = "prepare_user_action"
                guard_retried = True
                messages.append(SystemMessage(content=(
                    f"订单已确定：{active_order or active}；用户动作：{required_action}。"
                    f"现在必须调用 {action_tool} 并等待系统确认；如果政策不允许，调用 handoff_to_human 或明确解释，不要只文字询问。"
                )))
                continue
            if not active_order:
                found = set(ORDER_RE.findall(text))
                if len(found) == 1:
                    active_order = next(iter(found)).upper()
            await _force_handoff_if_ineligible(
                token, active_order or active, context.action or pending_action,
                last_text, text, thread_id,
            )
            _force_handoff_for_policy(last_text, thread_id)
            if ui_action is None:
                for item in trace:
                    if item.get("tool") != "prepare_user_action":
                        continue
                    try:
                        payload = json.loads(str(item.get("result")))
                        if payload.get("type") == "user_action":
                            ui_action = payload
                            break
                    except (TypeError, ValueError):
                        continue
            if ui_action is None:
                ui_action = await _fallback_user_action(
                    token, active_order or active, state.get("intent"), last_text, text
                )
            return {
                "reply": text,
                "messages": [AIMessage(content=text)],
                "reply_chain": "react",
                "tool_trace": trace,
                "react_fallback": False,
                "react_fallback_reason": None,
                "active_order_no": active_order,
                "active_order_at": active_at,
                "last_candidates": candidates[:5],
                "pending_write_action": pending_action,
                "ui_action": ui_action,
                "pending_user_action": pending_user_action,
                "candidates": candidates[:3],
            }

        messages.append(ai)
        for call in ai.tool_calls:
            name = call.get("name", "")
            args = call.get("args", {}) or {}
            call_id = call.get("id", f"call-{step}-{name}")
            write_types = {"create_refund": "REFUND", "create_return": "RETURN", "create_exchange": "EXCHANGE"}
            if name in write_types:
                explicit_order = context.order_no
                if not (active_order or active or explicit_order):
                    messages.append(ToolMessage(
                        content=_json({"error": "订单未定位，不能直接写；先 find_my_orders/query_order"}),
                        tool_call_id=call_id,
                    ))
                    continue
                if not (active_order or active) and len(candidates) > 1:
                    messages.append(ToolMessage(
                        content=_json({"error": "有多个候选订单，必须先确认是哪一单"}),
                        tool_call_id=call_id,
                    ))
                    continue
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
                quality = any(word in last_text for word in QUALITY_HINTS) or any(
                    word in reason for word in QUALITY_HINTS
                )
                intercepted = any(
                    item.get("tool") == "intercept_order" and "INTERCEPTED" in str(item.get("result", ""))
                    for item in trace
                )
                try:
                    eligibility = await business_api.order_eligibility(
                        order_no, as_type.lower(), token, quality=quality, intercepted=intercepted
                    )
                except Exception:  # noqa: BLE001
                    eligibility = {"allowed": False, "reason": "资格校验失败"}
                if not eligibility.get("allowed"):
                    messages.append(ToolMessage(
                        content=_json({"error": eligibility.get("reason") or "当前订单不满足售后条件"}),
                        tool_call_id=call_id,
                    ))
                    continue
                next_action = str(eligibility.get("nextAction") or "")
                if next_action in ("RETURN_FORM", "EXCHANGE_FORM"):
                    messages.append(ToolMessage(
                        content=_json({"error": "已签收退换必须先 prepare_user_action 收集原因"}),
                        tool_call_id=call_id,
                    ))
                    continue
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
                    active_at = clock.now(UTC).isoformat()
                    candidates = []
                    pending_action = None
                except Exception as exc:  # noqa: BLE001
                    trace.append({"step": step, "tool": name, "args": args, "error": str(exc)[:200]})
                    messages.append(ToolMessage(content=_json({"error": str(exc)[:200]}),
                                                tool_call_id=call_id))
                continue

            if name == "find_my_orders":
                args = context.apply_find_args(args)
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
                    "result": str(result) if name in ("find_my_orders", "prepare_user_action") else str(result)[:300],
                })
                messages.append(ToolMessage(content=str(result), tool_call_id=call_id))
                failures = 0
                order_no = args.get("order_no")
                if order_no and name in ("query_order", "query_logistics"):
                    active_order = str(order_no)
                    active_at = clock.now(UTC).isoformat()
                if name == "prepare_user_action":
                    try:
                        payload = result if isinstance(result, dict) else json.loads(str(result))
                        if payload.get("type") == "user_action":
                            ui_action = payload
                            pending_user_action = None
                    except (TypeError, ValueError):
                        pass
                if name == "find_my_orders":
                    try:
                        payload = json.loads(str(result))
                        found = payload.get("candidates") or []
                        if not found:
                            fallback_reason = "no_candidates"
                            break
                        candidates = found[:5]
                        if state.get("intent") in ("refund", "return", "exchange"):
                            pending_action = str(state.get("intent"))
                        if not active_order:
                            matched = []
                            if len(found) == 1:
                                matched = found
                            elif context.time_from and context.time_to:
                                key = "createdAt" if context.time_field == "created" else "deliveredAt"
                                matched = [
                                    item for item in found
                                    if item.get(key)
                                    and context.time_from <= str(item[key])[:10] <= context.time_to
                                ]
                            if len(matched) == 1:
                                active_order = str(matched[0].get("orderNo"))
                                active_at = clock.now(UTC).isoformat()
                    except (TypeError, ValueError):
                        pass
            except GraphInterrupt:
                raise
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

    if ui_action is not None:
        text = "请在表单中填写信息后提交。"
        return {
            "reply": text,
            "messages": [AIMessage(content=text)],
            "reply_chain": "react",
            "tool_trace": trace,
            "react_fallback": False,
            "react_fallback_reason": None,
            "active_order_no": active_order,
            "active_order_at": active_at,
            "ui_action": ui_action,
            "pending_user_action": None,
        }
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
