"""图节点：分类 → 知识/工具 → 人工 → 应答。

每个节点都只做一件事，并且把「失败」当成一等公民：
- 模型不可用 → 关键词兜底；
- 业务系统失败 → 转成结构化错误交给应答节点；
- 需要人工 → interrupt 挂起，恢复后继续。
"""

from __future__ import annotations

import re
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app.graph.state import AgentState
from app.llm.registry import ainvoke_with_fallback, with_structured_output
from app.observability.trace import node_span
from app.tools import business_api
from app.tools.business_api import BusinessAPIError

POLICY_TEXT = """【售后政策摘要】
1. 签收 7 天内支持无理由退货，商品需吊牌完好、不影响二次销售；
2. 质量问题 15 天内可换货/退款，需上传凭证；
3. 退款审核通过后 1-3 个工作日原路退回；
4. 物流超过 72 小时无更新可申请催件或补发。"""

ORDER_NO_PATTERN = re.compile(r"(CS\d{7,})", re.IGNORECASE)

Intent = Literal["order_query", "logistics", "refund", "policy", "complaint", "other"]


class Classification(BaseModel):
    intent: Intent = Field(description="用户意图")
    order_no: str | None = Field(default=None, description="订单号，用户没给则为空")
    reason: str | None = Field(default=None, description="退款/投诉原因")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


def _last_user_text(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


def _keyword_classify(text: str) -> Classification:
    """没有 API Key 或模型超时的兜底路径：保证本地永远能跑通。

    判定顺序很重要：先「投诉」再「政策」再「退款」。
    否则「退货政策几天」会被「退货」抢先判成 refund（早期测试就栽在这）。
    """
    match = ORDER_NO_PATTERN.search(text)
    order_no = match.group(1).upper() if match else None
    if any(k in text for k in ("投诉", "差评", "客服态度", "生气", "举报")):
        intent: Intent = "complaint"
    elif any(k in text for k in ("政策", "规则", "无理由", "能不能退", "几天内")):
        intent = "policy"
    elif any(k in text for k in ("退款", "退货", "退钱", "换货", "退掉", "退")):
        intent = "refund"
    elif any(k in text for k in ("物流", "快递", "到哪", "运单", "发货")):
        intent = "logistics"
    elif order_no or any(k in text for k in ("订单", "买的", "下单")):
        intent = "order_query"
    else:
        intent = "other"
    return Classification(intent=intent, order_no=order_no, reason=text[:100], confidence=0.4)


async def classify(state: AgentState) -> dict[str, Any]:
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    text = _last_user_text(state["messages"])

    with node_span(thread_id, "classify", user_text=text[:200]) as info:
        try:
            model = with_structured_output("fast", Classification)
            result = await model.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "你是电商售后意图分类器。只输出结构化结果。"
                            "intent 从 order_query/logistics/refund/policy/complaint/other 中选。"
                        )
                    ),
                    HumanMessage(content=text),
                ]
            )
            parsed = result if isinstance(result, Classification) else Classification.model_validate(result)
            info["source"] = "llm"
        except Exception as exc:  # noqa: BLE001 - 模型不可用必须降级
            parsed = _keyword_classify(text)
            info["source"] = "keyword"
            info["fallback_reason"] = str(exc)[:200]

        info["intent"] = parsed.intent
        return {
            "intent": parsed.intent,
            "order_no": parsed.order_no or (ORDER_NO_PATTERN.search(text).group(1).upper() if ORDER_NO_PATTERN.search(text) else None),
            "reason": parsed.reason,
            "confidence": parsed.confidence,
        }


def route_after_classify(state: AgentState) -> str:
    intent = state.get("intent", "other")
    if intent == "complaint":
        return "handoff"
    if intent in ("order_query", "logistics", "refund"):
        return "tools"
    if intent == "policy":
        return "knowledge"
    return "respond"


async def knowledge_node(state: AgentState) -> dict[str, Any]:
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    with node_span(thread_id, "knowledge"):
        # TODO(W1-D5): 换成 Chroma 检索，现在是整段政策注入
        return {"knowledge": POLICY_TEXT}


async def tool_node(state: AgentState) -> dict[str, Any]:
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    intent = state.get("intent", "other")
    order_no = state.get("order_no")
    reason = state.get("reason") or ""

    with node_span(thread_id, "tools", intent=intent, order_no=order_no) as info:
        if not order_no:
            info["result"] = "missing_order_no"
            return {"tool_result": {"tool": intent, "error": "missing_order_no", "recoverable": True}}
        try:
            if intent == "order_query":
                data = await business_api.get_order(order_no)
            elif intent == "logistics":
                data = await business_api.get_logistics(order_no)
            else:
                data = await business_api.apply_refund(order_no, reason)
            info["result"] = "ok"
            return {"tool_result": data}
        except BusinessAPIError as exc:
            info["result"] = "error"
            info["error"] = str(exc)[:200]
            return {"tool_result": {"tool": intent, "error": str(exc), "recoverable": True}}


async def handoff_prepare(state: AgentState) -> dict[str, Any]:
    """转人工第一步：先把「已转接」的答复写进状态，再去挂起。

    顺序不能反：``interrupt()`` 一执行，节点就中断、返回值不会落到状态里，
    用户在界面上就会看到一条空回复（c07 的 bug 就是这么来的）。
    正确姿势是「先落盘、再挂起」——这也是生产 Agent 恢复时能无缝续上的关键。
    """
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    with node_span(thread_id, "handoff_prepare"):
        return {
            "needs_human": True,
            "handoff_reason": state.get("intent", "complaint"),
            "handoff_summary": _last_user_text(state["messages"]),
            "reply": "已为您转接人工客服，人工将在 3 分钟内接入，请稍候。",
        }


async def await_human(state: AgentState) -> dict[str, Any]:
    """转人工第二步：真正的挂起点。恢复后拿到审批结果。"""
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    decision = interrupt(
        {
            "type": "human_handoff",
            "thread_id": thread_id,
            "reason": state.get("handoff_reason", "complaint"),
            "summary": state.get("handoff_summary", ""),
        }
    )
    approved = bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision)

    with node_span(thread_id, "await_human", approved=approved):
        return {"handoff_approved": approved}


def _template_reply(state: AgentState) -> str:
    intent = state.get("intent", "other")
    tool_result = state.get("tool_result") or {}
    if tool_result.get("error") == "missing_order_no":
        return "请提供您的订单号（例如 CS2024001），我马上帮您查询。"
    if tool_result.get("error"):
        return f"抱歉，暂时查不到该订单：{tool_result['error']}。您可以稍后重试或转人工。"

    if intent == "order_query" and tool_result:
        return (
            f"订单 {tool_result.get('orderNo')}：{tool_result.get('item')}，"
            f"金额 {tool_result.get('amount')} 元，状态 {tool_result.get('status')}，"
            f"下单日期 {tool_result.get('createdAt')}。"
        )
    if intent == "logistics" and tool_result:
        traces = "；".join(tool_result.get("traces", [])[-2:]) or "暂无轨迹"
        return (
            f"您的包裹由 {tool_result.get('carrier')} 承运，运单号 {tool_result.get('trackingNo')}，"
            f"当前状态：{tool_result.get('status')}。最新轨迹：{traces}。"
        )
    if intent == "refund" and tool_result:
        return (
            f"退款申请已提交，单号 {tool_result.get('refundNo')}，"
            f"当前状态 {tool_result.get('status')}，审核通过后 1-3 个工作日原路退回。"
        )
    return state.get("knowledge", POLICY_TEXT)


async def respond_node(state: AgentState) -> dict[str, Any]:
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    if state.get("needs_human"):
        # 转人工的答复已在 handoff_prepare 里写好；这里只在「人工驳回」时改写。
        if state.get("handoff_approved") is False:
            return {"reply": "已记录您的投诉，我们会安排专员在 24 小时内回访，感谢您的反馈。"}
        return {}

    context = {
        "intent": state.get("intent"),
        "order_no": state.get("order_no"),
        "tool_result": state.get("tool_result"),
        "knowledge": state.get("knowledge"),
        "policy": POLICY_TEXT,
    }
    template = _template_reply(state)

    with node_span(thread_id, "respond", intent=state.get("intent")) as info:
        try:
            msg = await ainvoke_with_fallback(
                [
                    SystemMessage(
                        content=(
                            "你是电商售后客服。根据给定的事实（订单/物流/退款数据、政策）回复用户。"
                            "只能陈述事实里有的信息，不要编造；语气简洁、有同理心，不超过 120 字。"
                        )
                    ),
                    HumanMessage(content=f"事实：{context}\n\n用户：{_last_user_text(state['messages'])}"),
                ]
            )
            info["source"] = "llm"
            return {"reply": str(msg.content).strip() or template}
        except Exception as exc:  # noqa: BLE001 - 模型不可用仍要能答
            info["source"] = "template"
            info["fallback_reason"] = str(exc)[:200]
            return {"reply": template}
