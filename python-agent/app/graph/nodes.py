"""图节点：分类 → 知识/工具 → 人工 → 应答。

每个节点都只做一件事，并且把「失败」当成一等公民：
- 模型不可用 → 关键词兜底；
- 业务系统失败 → 转成结构化错误交给应答节点；
- 需要人工 → interrupt 挂起，恢复后继续。
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app.graph.state import AgentState
from app.knowledge import store as knowledge_store
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
SKU_PATTERN = re.compile(r"(SKU\d{4})", re.IGNORECASE)

# SPEC §8：单会话最多 10 轮，超过后不再调用模型/工具，直接转人工兜底
MAX_TURNS = 10
TURN_LIMIT_REPLY = "本次会话轮次已达上限（10 轮），已为您转接人工坐席，请稍候。"

# 用户很少报 SKU，多数说商品名；这里做一层最简映射（真实系统应查商品目录）
PRODUCT_SKU_HINTS: dict[str, str] = {
    "跑步鞋": "SKU1001",
    "运动鞋": "SKU1001",
    "鞋": "SKU1001",
    "耳机": "SKU1002",
    "行李箱": "SKU1003",
    "登机箱": "SKU1003",
}

Intent = Literal["order_query", "logistics", "refund", "policy", "complaint", "product_info", "other"]


class Classification(BaseModel):
    intent: Intent = Field(description="用户意图")
    order_no: str | None = Field(default=None, description="订单号，用户没给则为空")
    sku: str | None = Field(default=None, description="商品 SKU，用户没给则为空")
    reason: str | None = Field(default=None, description="退款/投诉原因")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


def _last_user_text(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


def _guess_sku(text: str) -> str | None:
    match = SKU_PATTERN.search(text)
    if match:
        return match.group(1).upper()
    for hint, sku in PRODUCT_SKU_HINTS.items():
        if hint in text:
            return sku
    return None


def _refusal(text: str) -> str | None:
    """SPEC §9 四类拒答，各一句标准话术；判定顺序：违规 → 越权 → 竞品 → 无关。"""
    privacy = any(k in text for k in ("手机号", "电话", "地址", "身份证", "住哪", "住址", "家住"))
    about_others = any(
        k in text for k in ("他的", "她的", "别人的", "对方的", "买家", "客户", "其他人", "buyer_")
    )
    fabrication = any(k in text for k in ("编一个", "编个", "虚构", "随便编", "假设一个订单"))
    ghostwriting = any(k in text for k in ("写作业", "代写", "写论文"))
    if (privacy and about_others) or fabrication or ghostwriting:
        return "这个我没法帮您，我们继续处理售后问题吧。"

    if any(k in text for k in ("别人", "他人", "朋友的")) and any(
        k in text for k in ("订单", "物流", "售后", "单号")
    ):
        return "我这边只能处理您本人订单的问题哦～"

    if any(k in text for k in ("对比", "比怎么样", "比你们", "友商", "竞品")) or "和" in text and "比" in text:
        return "我只负责售后问题，具体对比建议参考官方参数页。"

    delay_context = any(k in text for k in ("订单", "物流", "单号", "快递", "派送"))
    if "天气" in text and delay_context:
        return None  # 「天气原因延误」是合法物流咨询
    if any(
        k in text
        for k in ("天气", "写诗", "写首诗", "写代码", "写个代码", "翻译", "笑话", "股票", "故事", "做饭")
    ):
        return "我是售后客服，可以帮您查订单、物流或办理售后。"

    return None


def _keyword_classify(text: str) -> Classification:
    """没有 API Key 或模型超时的兜底路径：保证本地永远能跑通。

    判定顺序很重要：投诉 → 政策 → 退款 → 商品 → 物流 → 订单。
    「退货政策几天」必须先判政策，「尺码不合适」这类商品咨询不能抢在退款前面。
    """
    match = ORDER_NO_PATTERN.search(text)
    order_no = match.group(1).upper() if match else None
    sku = _guess_sku(text)

    if any(k in text for k in ("投诉", "差评", "客服态度", "生气", "举报", "欺骗", "举报")):
        intent: Intent = "complaint"
    elif any(
        k in text
        for k in (
            "政策", "规则", "能不能退", "几天内",
            "发票", "价保", "运费", "到账", "流程", "隐私", "手机号", "多少天", "几天",
        )
    ):
        intent = "policy"
    elif any(k in text for k in ("退款", "退货", "退钱", "换货", "退掉", "退")):
        intent = "refund"
    elif sku or any(
        k in text
        for k in ("续航", "尺码", "材质", "库存", "多少钱", "编码", "降噪", "轮子", "能带", "适合", "参数", "支持")
    ):
        intent = "product_info"
    elif "订单号" in text:
        # 「订单号」里含「单号」，必须在物流分支之前拦截
        intent = "order_query"
    elif any(k in text for k in ("物流", "快递", "到哪", "运单", "发货", "单号", "签收", "催", "派送", "到货", "运输", "轨迹")):
        intent = "logistics"
    elif order_no or any(k in text for k in ("订单", "买的", "下单")):
        intent = "order_query"
    else:
        intent = "other"
    return Classification(intent=intent, order_no=order_no, sku=sku, reason=text[:100], confidence=0.4)


async def classify(state: AgentState) -> dict[str, Any]:
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    text = _last_user_text(state["messages"])

    # SPEC §8：turn_count > 10 走转人工兜底，且不再调用模型/工具
    turn_count = int(state.get("turn_count") or 0) + 1
    if turn_count > MAX_TURNS:
        with node_span(thread_id, "classify", user_text=text[:200]) as info:
            info["source"] = "turn_limit"
            info["turn_count"] = turn_count
        return {
            "turn_count": turn_count,
            "turn_limit": True,
            "intent": "other",
            "needs_human": True,
            "refusal": None,
            "safety_reply": None,
            "order_no": None,
            "sku": None,
            "reason": None,
            "confidence": 1.0,
        }

    # SPEC §9：拒答在分类之前、模型之前判定，避免为拒答问题调用模型
    refusal = _refusal(text)
    if refusal:
        with node_span(thread_id, "classify", user_text=text[:200]) as info:
            info["source"] = "refusal"
            info["intent"] = "other"
        return {
            "turn_count": turn_count,
            "turn_limit": False,
            "intent": "other",
            "refusal": refusal,
            "safety_reply": None,
            "order_no": None,
            "sku": None,
            "reason": None,
            "confidence": 1.0,
        }

    with node_span(thread_id, "classify", user_text=text[:200]) as info:
        try:
            model = with_structured_output("fast", Classification)
            result = await model.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "你是电商售后意图分类器。只输出结构化结果。"
                            "intent 从 order_query/logistics/refund/policy/complaint/product_info/other 中选。"
                            "用户问商品参数（续航、尺码、材质、库存、价格）时选 product_info。"
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
            "turn_count": turn_count,
            "turn_limit": False,
            # 每轮清空拒答状态，避免上一轮的拒答话术粘住后续对话
            "refusal": None,
            "safety_reply": None,
            "order_no": parsed.order_no
            or (ORDER_NO_PATTERN.search(text).group(1).upper() if ORDER_NO_PATTERN.search(text) else None),
            "sku": parsed.sku or _guess_sku(text),
            "reason": parsed.reason,
            "confidence": parsed.confidence,
        }


async def refuse(state: AgentState) -> dict[str, Any]:
    """SPEC §8 的 refuse 分支：只写标准话术，交给 respond 输出。"""
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    with node_span(thread_id, "refuse") as info:
        info["category"] = "refusal"
    return {"safety_reply": state.get("refusal") or ""}


def route_after_classify(state: AgentState) -> str:
    if state.get("turn_limit"):
        return "respond"
    if state.get("refusal"):
        return "refuse"
    intent = state.get("intent", "other")
    if intent == "complaint":
        return "handoff"
    if intent in ("order_query", "logistics", "refund", "product_info"):
        return "tools"
    return "respond"


async def tool_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    intent = state.get("intent", "other")
    order_no = state.get("order_no")
    sku = state.get("sku")
    reason = state.get("reason") or ""

    with node_span(thread_id, "tools", intent=intent, order_no=order_no, sku=sku) as info:
        # 商品咨询只需要 SKU，不需要订单号
        if intent == "product_info":
            if not sku:
                info["result"] = "missing_sku"
                return {"tool_result": {"tool": intent, "error": "missing_sku", "recoverable": True}}
            try:
                token = (config or {}).get("configurable", {}).get("auth_token") or ""
                data = await business_api.get_product(sku, token)
                info["result"] = "ok"
                return {"tool_result": data}
            except BusinessAPIError as exc:
                info["result"] = "error"
                info["error"] = str(exc)[:200]
                return {"tool_result": {"tool": intent, "error": str(exc), "recoverable": True}}

        if not order_no:
            info["result"] = "missing_order_no"
            return {"tool_result": {"tool": intent, "error": "missing_order_no", "recoverable": True}}
        token = (config or {}).get("configurable", {}).get("auth_token") or ""
        if not token:
            info["result"] = "unauthorized"
            return {"tool_result": {"tool": intent, "error": "UNAUTHORIZED: 缺少登录令牌",
                                    "recoverable": False}}
        try:
            if intent == "order_query":
                data = await business_api.get_order(order_no, token)
            elif intent == "logistics":
                data = await business_api.get_logistics(order_no, token)
            else:
                as_type = _infer_after_sales_type(_last_user_text(state["messages"]))
                data = await business_api.apply_after_sales(order_no, as_type, reason, token)
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
        text = "已为您转接人工客服，人工将在 3 分钟内接入，请稍候。"
        return {
            "needs_human": True,
            "handoff_reason": state.get("intent", "complaint"),
            "handoff_summary": _last_user_text(state["messages"]),
            "reply": text,
            "messages": [AIMessage(content=text)],
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


def _infer_after_sales_type(text: str) -> str:
    """从用户话术推断售后类型；判不出来按退款处理。"""
    if "换货" in text:
        return "EXCHANGE"
    if "退货" in text or "寄回" in text:
        return "RETURN"
    return "REFUND"


def _template_reply(state: AgentState) -> str:
    intent = state.get("intent", "other")
    tool_result = state.get("tool_result") or {}

    # 政策回答优先于上一轮遗留的工具错误：多轮里 tool_result 不会被清空，
    # 先判 error 会把「退货政策几天」答成「请提供订单号」。
    if intent == "policy" and state.get("knowledge"):
        refs = state.get("policy_refs") or []
        suffix = f"\n\n依据：{'、'.join(f'[{c}]' for c in refs)}" if refs else ""
        return f"{state['knowledge']}{suffix}"

    if tool_result.get("error") == "missing_order_no":
        return "请提供您的订单号（例如 CS2024001），我马上帮您查询。"
    if tool_result.get("error") == "missing_sku":
        return "请告诉我具体是哪个商品（例如轻量跑步鞋 / 降噪耳机 / 登机行李箱），我帮您查参数。"
    if "MISSING_SLOT" in str(tool_result.get("error", "")):
        return "请补充订单号或售后原因后再试。"
    if "NOT_FOUND" in str(tool_result.get("error", "")) or "DENIED" in str(tool_result.get("error", "")):
        # 越权与不存在同口径（ADR-0001）；不区分订单/物流/商品，避免说错资源名
        return "没有找到对应的记录，请核对信息后重试。"
    if "INVALID_INPUT" in str(tool_result.get("error", "")):
        return "提交的信息不符合要求，请检查后重试。"
    if "UNAUTHORIZED" in str(tool_result.get("error", "")):
        return "登录状态已过期，请重新登录后再试。"
    if tool_result.get("error"):
        # 不把内部错误码/堆栈透给用户
        return "系统暂时不可用，请稍后重试。"

    if intent == "product_info" and tool_result:
        attrs = "，".join(f"{k}{v}" for k, v in (tool_result.get("attrs") or {}).items())
        return (
            f"{tool_result.get('name')}（{tool_result.get('sku')}），"
            f"售价 {tool_result.get('price')} 元，库存 {tool_result.get('stock')} 件。{attrs}。"
        )
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
        type_label = {"REFUND": "退款", "RETURN": "退货", "EXCHANGE": "换货"}.get(
            tool_result.get("type"), "售后"
        )
        return (
            f"您的{type_label}申请已提交，单号 {tool_result.get('requestNo')}，"
            f"当前状态 {tool_result.get('status')}，审核通过后 1-3 个工作日处理。"
        )
    if intent == "policy" and not state.get("knowledge"):
        # 检索无命中时不能拿整段政策摘要冒充答案
        return "没有查到对应的政策条款，建议转人工确认，避免给您错误信息。"
    if intent == "other" and not state.get("knowledge") and not tool_result:
        # 闲聊/无法归类的输入：明确说能做什么，而不是倾倒政策摘要
        return "我是售后客服，可以帮您查订单、物流或办理售后。"
    # 检索无命中时 knowledge 为 None，必须回落到政策摘要，不能把 None 塞给模型
    return state.get("knowledge") or POLICY_TEXT


def _with_citation(text: str, refs: list[str]) -> str:
    """确保回答带引用：模型可能忽略提示词，这里兜底补一行「依据」。"""
    if not refs or re.search(r"\[P\d{2}\]", text):
        return text
    return f"{text}\n\n依据：{'、'.join(f'[{c}]' for c in refs)}"


async def respond_node(state: AgentState) -> dict[str, Any]:
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    if state.get("turn_limit"):
        text = TURN_LIMIT_REPLY
        with node_span(thread_id, "respond", intent="turn_limit") as info:
            info["source"] = "template"
            info["reason"] = "turn_limit"
        return {"reply": text, "messages": [AIMessage(content=text)]}
    if state.get("refusal") and state.get("safety_reply"):
        text = str(state["safety_reply"])
        with node_span(thread_id, "respond", intent="refusal") as info:
            info["source"] = "template"
            info["reason"] = "refusal"
        return {"reply": text, "messages": [AIMessage(content=text)]}
    if state.get("needs_human"):
        # 转人工的答复已在 handoff_prepare 里写好；这里只在「人工驳回」时改写。
        if state.get("handoff_approved") is False:
            text = "已记录您的投诉，我们会安排专员在 24 小时内回访，感谢您的反馈。"
            return {"reply": text, "messages": [AIMessage(content=text)]}
        return {}

    # SPEC §8：生成回复前先检索；只有分数过阈值的片段进入上下文
    retrieval = await asyncio.to_thread(knowledge_store.retrieve, _last_user_text(state["messages"]))
    knowledge = retrieval.knowledge
    policy_refs = retrieval.policy_refs
    view: AgentState = {**state, "knowledge": knowledge, "policy_refs": policy_refs}

    context = {
        "intent": state.get("intent"),
        "order_no": state.get("order_no"),
        "tool_result": state.get("tool_result"),
        "knowledge": knowledge,
        "policy": POLICY_TEXT,
    }
    template = _template_reply(view)

    # 拒答与工具错误必须措辞确定：不交给模型改写（否则同一错误会出现不同说法）
    if (state.get("tool_result") or {}).get("error") or (
        state.get("intent") == "policy" and not knowledge
    ):
        return {
            "reply": template,
            "messages": [AIMessage(content=template)],
            "knowledge": knowledge,
            "policy_refs": policy_refs,
        }

    with node_span(thread_id, "respond", intent=state.get("intent")) as info:
        info["retrieval"] = retrieval.source
        info["policy_refs"] = policy_refs
        try:
            msg = await ainvoke_with_fallback(
                [
                    SystemMessage(
                        content=(
                            "你是电商售后客服。根据给定的事实（订单/物流/退款数据、政策）回复用户。"
                            "只能陈述事实里有的信息，不要编造；语气简洁、有同理心，不超过 120 字。"
                            "引用政策时必须保留 [Pxx] 编号，不要改写或省略。"
                        )
                    ),
                    HumanMessage(content=f"事实：{context}\n\n用户：{_last_user_text(state['messages'])}"),
                ]
            )
            info["source"] = "llm"
            text = _with_citation(str(msg.content).strip() or template, policy_refs)
            # 回复必须写回 messages，否则下一轮上下文里只有用户的话，没有 Agent 的答复
            return {
                "reply": text,
                "messages": [AIMessage(content=text)],
                "knowledge": knowledge,
                "policy_refs": policy_refs,
            }
        except Exception as exc:  # noqa: BLE001 - 模型不可用仍要能答
            info["source"] = "template"
            info["fallback_reason"] = str(exc)[:200]
            return {
                "reply": template,
                "messages": [AIMessage(content=template)],
                "knowledge": knowledge,
                "policy_refs": policy_refs,
            }
