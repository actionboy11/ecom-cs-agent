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

# SPEC §8：单会话最多 10 轮，超过后不调模型/工具，直接转人工（真实挂起）
MAX_TURNS = 10
TURN_LIMIT_REPLY = f"本次会话轮次已达上限（{MAX_TURNS} 轮），已为您转接人工客服，请稍候。"

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
    turn_count = int(state.get("turn_count") or 0) + 1

    # SPEC §9：拒答在分类之前、模型之前判定（轮次上限也排在拒答之后）
    refusal = _refusal(text)
    if refusal:
        with node_span(thread_id, "classify", user_text=text[:200]) as info:
            info["source"] = "refusal"
            info["intent"] = "other"
        return {
            "turn_count": turn_count,
            "intent": "other",
            "refusal": refusal,
            "safety_reply": None,
            "tool_result": None,
            "order_no": None,
            "sku": None,
            "reason": None,
            "confidence": 1.0,
            "tasks": [],
        }

    # SPEC §8：turn_count > 10 转人工（真实挂起），且不再调用模型/工具
    if turn_count > MAX_TURNS:
        with node_span(thread_id, "classify", user_text=text[:200]) as info:
            info["source"] = "turn_limit"
            info["turn_count"] = turn_count
        return {
            "turn_count": turn_count,
            "intent": "other",
            "refusal": None,
            "safety_reply": None,
            "tool_result": None,
            "order_no": None,
            "sku": None,
            "reason": None,
            "confidence": 1.0,
            "tasks": [],
        }

    # 待确认计划：用户说「确认/执行」才真正调工具；说「取消」则清空
    if state.get("awaiting_confirm"):
        if any(word in text for word in ("确认", "执行", "可以", "好的", "是的", "没问题", "ok", "OK")):
            with node_span(thread_id, "classify", user_text=text[:200]) as info:
                info["source"] = "confirm"
            return {
                "intent": "multi",
                "tasks": state.get("pending_tasks") or [],
                "pending_tasks": [],
                "pending_actions": [],
                "awaiting_confirm": False,
                "cancelled": False,
                "turn_count": turn_count,
                "refusal": None,
                "safety_reply": None,
                "tool_result": None,
                "order_no": None,
                "sku": None,
                "reason": None,
                "confidence": 1.0,
            }
        if any(word in text for word in ("取消", "不用了", "算了", "先不")):
            with node_span(thread_id, "classify", user_text=text[:200]) as info:
                info["source"] = "cancel"
            return {
                "intent": "other",
                "tasks": [],
                "pending_tasks": [],
                "pending_actions": [],
                "awaiting_confirm": False,
                "cancelled": True,
                "turn_count": turn_count,
                "refusal": None,
                "safety_reply": None,
                "tool_result": None,
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
        intent = _apply_hard_rules(text, parsed.intent)
        tasks = _extract_tasks(text)
        info["hard_rule_intent"] = intent if intent != parsed.intent else None
        info["tasks"] = len(tasks)
        return {
            "intent": intent,
            "tasks": [],
            "pending_tasks": tasks,
            "pending_actions": [],
            "awaiting_confirm": bool(tasks),
            "cancelled": False,
            "turn_count": turn_count,
            # 每轮清空拒答状态与上轮工具结果，避免旧数据串到本轮回复
            "refusal": None,
            "safety_reply": None,
            "tool_result": None,
            "order_no": parsed.order_no
            or (ORDER_NO_PATTERN.search(text).group(1).upper() if ORDER_NO_PATTERN.search(text) else None),
            "sku": parsed.sku or _guess_sku(text),
            "reason": parsed.reason,
            "confidence": parsed.confidence,
            "urgent": any(hint in text for hint in URGENT_HINTS),
        }


async def refuse(state: AgentState) -> dict[str, Any]:
    """SPEC §8 的 refuse 分支：只写标准话术，交给 respond 输出。"""
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    with node_span(thread_id, "refuse") as info:
        info["category"] = "refusal"
    return {"safety_reply": state.get("refusal") or ""}


EXCEPTION_HINTS = ("拆封", "定制", "超过", "赠品", "七天", "十五天", "无理由", "价保")
REFERENCE_HINTS = ("那个", "昨天", "上周", "前两天", "刚买", "之前")
PRODUCT_HINTS = {"耳机": "耳机", "行李箱": "行李箱", "杯子": "保温杯", "鞋": "跑步鞋", "背包": "背包", "充电宝": "充电宝"}
URGENT_HINTS = ("很急", "今天必须", "尽快", "马上", "快点", "着急")
TASK_SPLIT = re.compile(r"[，,；;。]|另外|顺便|再|还有")


def _extract_tasks(text: str) -> list[dict[str, Any]]:
    """把「退款 + 催件」这类一句话拆成多个动作；政策问答不算动作。"""
    tasks: list[dict[str, Any]] = []
    for part in TASK_SPLIT.split(text):
        part = part.strip()
        if len(part) < 2:
            continue
        order = ORDER_NO_PATTERN.search(part)
        if any(k in part for k in ("投诉", "差评", "破服务", "态度")):
            intent = "complaint"
        elif any(k in part for k in ("催", "物流", "到哪", "快递")):
            intent = "logistics"
        elif any(k in part for k in ("退", "换")):
            intent = "refund"
        else:
            continue
        task = {
            "intent": intent,
            "order_no": order.group(1).upper() if order else None,
            "text": part,
        }
        if task not in tasks:
            tasks.append(task)
    action_intents = {t["intent"] for t in tasks if t["intent"] != "complaint"}
    distinct_intents = {t["intent"] for t in tasks}
    return tasks if len(tasks) >= 2 and len(distinct_intents) >= 2 and action_intents else []


def _apply_hard_rules(text: str, intent: str) -> str:
    """分类器的确定性兜底：政策例外、模糊指代、投诉/加急、价保。"""
    has_order = bool(ORDER_NO_PATTERN.search(text))
    # 赠品没有明确政策条款：转人工确认，避免套用商品条款
    if "赠品" in text:
        return "complaint"
    if any(hint in text for hint in EXCEPTION_HINTS) and not has_order:
        return "policy"
    if (
        not has_order
        and any(hint in text for hint in REFERENCE_HINTS)
        and (any(p in text for p in PRODUCT_HINTS) or any(w in text for w in ("有问题", "坏了", "漏水")))
    ):
        return "order_query"
    if any(hint in text for hint in ("投诉", "破服务", "差评", "态度")):
        return "complaint"
    if any(hint in text for hint in URGENT_HINTS) and intent not in (
        "refund", "logistics", "order_query", "product_info"
    ):
        return "complaint"
    if any(hint in text for hint in ("降价", "补差", "价保")) and not has_order:
        return "refund"
    if any(hint in text for hint in ("换货", "换一码", "换大", "换小", "换码")) and not has_order:
        return "refund"
    return intent


def route_after_classify(state: AgentState) -> str:
    if state.get("refusal"):
        return "refuse"
    # SPEC §8：超过轮次上限转人工（真实挂起，可被坐席恢复）
    if int(state.get("turn_count") or 0) > MAX_TURNS:
        return "handoff"
    if state.get("awaiting_confirm"):
        return "respond"
    if state.get("tasks"):
        return "tools"
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
        tasks = state.get("tasks") or []
        if tasks:
            token = (config or {}).get("configurable", {}).get("auth_token") or ""
            if not token:
                return {"tool_result": {"tool": "multi", "error": "UNAUTHORIZED: 缺少登录令牌"}}
            results: list[dict[str, Any]] = []
            for task in tasks:
                task_intent = task.get("intent", "other")
                task_order = task.get("order_no")
                if task_intent == "complaint":
                    results.append({"intent": "complaint", "tool": "handoff", "data": {"needs_human": True}})
                    continue
                if not task_order:
                    try:
                        orders = await business_api.list_orders(token)
                    except BusinessAPIError as exc:
                        results.append({"intent": task_intent, "tool": "list_my_orders",
                                        "error": str(exc)[:200]})
                        continue
                    text = task.get("text", "")
                    matched = [
                        o for o in orders
                        if any(hint in text and keyword in (o.get("item") or o.get("itemName") or "")
                               for hint, keyword in PRODUCT_HINTS.items())
                    ]
                    if len(matched) == 1:
                        task_order = matched[0].get("orderNo")
                    else:
                        results.append({"intent": task_intent, "tool": "list_my_orders",
                                        "data": {"orders": orders}})
                        continue
                try:
                    if task_intent == "logistics":
                        data = await business_api.get_logistics(task_order, token)
                        tool_name = "query_logistics"
                    elif task_intent == "refund":
                        as_type = _infer_after_sales_type(task.get("text", ""))
                        as_reason = reason or task.get("text") or "用户申请退款"
                        data = await business_api.apply_after_sales(task_order, as_type, as_reason, token)
                        tool_name = "create_after_sales_request"
                    else:
                        data = await business_api.get_order(task_order, token)
                        tool_name = "query_order"
                    results.append({"intent": task_intent, "tool": tool_name, "data": data})
                except BusinessAPIError as exc:
                    results.append({"intent": task_intent, "tool": task_intent,
                                    "error": str(exc)[:200]})
            info["result"] = "multi"
            info["tasks"] = len(results)
            return {"tool_result": {"tool": "multi", "data": {"results": results}}}

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
            token = (config or {}).get("configurable", {}).get("auth_token") or ""
            if not token:
                info["result"] = "unauthorized"
                return {"tool_result": {"tool": intent, "error": "UNAUTHORIZED: 缺少登录令牌",
                                        "recoverable": False}}
            try:
                orders = await business_api.list_orders(token)
            except BusinessAPIError as exc:
                info["result"] = "error"
                info["error"] = str(exc)[:200]
                return {"tool_result": {"tool": "list_my_orders", "error": str(exc), "recoverable": True}}
            text = _last_user_text(state["messages"])
            matched = [
                o for o in orders
                if any(hint in text and keyword in (o.get("item") or o.get("itemName") or "")
                       for hint, keyword in PRODUCT_HINTS.items())
            ]
            candidates = matched or orders
            info["result"] = "candidates"
            info["candidate_count"] = len(candidates)
            return {"tool_result": {"tool": "list_my_orders", "data": {"orders": candidates}}}
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
                as_reason = reason or _last_user_text(state["messages"]) or "用户申请退款"
                data = await business_api.apply_after_sales(order_no, as_type, as_reason, token)
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
    over_limit = int(state.get("turn_count") or 0) > MAX_TURNS
    with node_span(thread_id, "handoff_prepare", reason="turn_limit" if over_limit else "complaint"):
        if over_limit:
            text = TURN_LIMIT_REPLY
        elif "赠品" in _last_user_text(state["messages"]):
            text = "赠品单独退换没有明确的政策条款，为避免误导，已为您转接人工确认。"
        elif any(word in _last_user_text(state["messages"]) for word in URGENT_HINTS):
            text = "已为您加急处理，请提供订单号和具体问题，我马上跟进；同时已转接人工优先处理。"
        else:
            text = "非常抱歉给您带来不好的体验，请告诉我是哪一单、具体什么问题，我先帮您处理；同时已转接人工优先处理。"
        return {
            "needs_human": True,
            "handoff_reason": "turn_limit" if over_limit else state.get("intent", "complaint"),
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

    # 政策回答优先于工具错误：classify 每轮会清空 tool_result，
    # 但同一轮里工具报错后再问政策的情况仍需兜底，先判 error 会把政策答成「请提供订单号」。
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
        return "请告诉我是哪一单、遇到什么问题（退款、换货、物流或投诉），我帮您处理。"
    # 检索无命中时 knowledge 为 None，必须回落到政策摘要，不能把 None 塞给模型
    return state.get("knowledge") or POLICY_TEXT


def _with_citation(text: str, refs: list[str]) -> str:
    """确保回答带引用：模型可能忽略提示词，这里兜底补一行「依据」。"""
    if not refs or re.search(r"\[P\d{2}\]", text):
        return text
    return f"{text}\n\n依据：{'、'.join(f'[{c}]' for c in refs)}"


async def respond_node(state: AgentState) -> dict[str, Any]:
    thread_id = state.get("thread_id", "unknown")  # type: ignore[arg-type]
    if state.get("awaiting_confirm") and state.get("pending_tasks"):
        tasks = state.get("pending_tasks") or []
        labels = {
            "refund": "退款/退货",
            "logistics": "催件/物流",
            "complaint": "转人工投诉",
        }
        lines = [f"{index + 1}. {labels.get(t.get('intent', ''), t.get('intent', ''))}"
                 f"（{t.get('order_no') or '待确认订单'}）"
                 for index, t in enumerate(tasks)]
        text = "我准备执行：\n" + "\n".join(lines) + "\n\n确认后我就开始办理，回复「确认」或「取消」。"
        actions = [
            {
                "intent": t.get("intent"),
                "order_no": t.get("order_no"),
                "label": labels.get(t.get("intent", ""), t.get("intent", "")),
            }
            for t in tasks
        ]
        with node_span(thread_id, "respond", intent="confirm_plan") as info:
            info["source"] = "template"
            info["tasks"] = len(tasks)
        return {
            "reply": text,
            "messages": [AIMessage(content=text)],
            "reply_chain": "template",
            "pending_actions": actions,
        }
    if state.get("cancelled"):
        text = "好的，已取消，没有执行任何操作。"
        with node_span(thread_id, "respond", intent="cancelled"):
            pass
        return {"reply": text, "messages": [AIMessage(content=text)], "reply_chain": "template"}
    if state.get("refusal") and state.get("safety_reply"):
        text = str(state["safety_reply"])
        with node_span(thread_id, "respond", intent="refusal") as info:
            info["source"] = "template"
            info["reason"] = "refusal"
        return {"reply": text, "messages": [AIMessage(content=text)], "reply_chain": "template"}
    if state.get("needs_human"):
        is_turn_limit = state.get("handoff_reason") == "turn_limit"
        if state.get("handoff_approved") is False:
            text = (
                "人工未接入，请继续描述您的问题。"
                if is_turn_limit
                else "已记录您的投诉，我们会安排专员在 24 小时内回访，感谢您的反馈。"
            )
        else:
            text = "人工已接入，请继续描述您的问题。"
        updates: dict[str, Any] = {
            "reply": text,
            "messages": [AIMessage(content=text)],
            "reply_chain": "template",
            "needs_human": False,
        }
        if is_turn_limit:
            # 重置轮次，避免恢复后第 12 条消息立刻再次挂起
            updates["turn_count"] = 0
            updates["handoff_reason"] = None
        return updates

    # SPEC §8：生成回复前先检索；只有分数过阈值的片段进入上下文
    retrieval = await asyncio.to_thread(knowledge_store.retrieve, _last_user_text(state["messages"]))
    knowledge = retrieval.knowledge
    policy_refs = retrieval.policy_refs
    # 身份/隐私条款只用于政策问答；业务查询里引用它会让用户以为还要核验身份
    if state.get("intent") != "policy":
        policy_refs = [ref for ref in policy_refs if ref not in ("P10", "P12")]
    view: AgentState = {**state, "knowledge": knowledge, "policy_refs": policy_refs}

    context = {
        "intent": state.get("intent"),
        "order_no": state.get("order_no"),
        "tool_result": state.get("tool_result"),
        "knowledge": knowledge,
        "policy": POLICY_TEXT,
        "urgent": bool(state.get("urgent")),
    }
    template = _template_reply(view)

    # 拒答与工具错误必须措辞确定：不交给模型改写（否则同一错误会出现不同说法）
    if (state.get("tool_result") or {}).get("error") or (
        state.get("intent") == "policy" and not knowledge
    ):
        return {
            "reply": template,
            "messages": [AIMessage(content=template)],
            "reply_chain": "template",
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
                            "用户身份已由系统登录态验证：不要要求用户提供手机号、身份证或验证码，也不要以此为由拒绝查询本人订单。"
                            "如果事实里是候选订单列表：主动指出最可能的订单（按商品、时间匹配），并请用户确认，不要只回“请提供订单号”。"
                            "如果是政策适用/例外问题（拆封、定制、超期、赠品）：先判断规则是否适用、例外条件是什么，再给下一步；不要先要订单号。"
                            "对拆封/定制/超期/赠品必须明确回答“属于/不属于例外、依据哪条”，不能只复述条款；政策没有规定时说明没有相关规定并建议转人工，不要套用其他条款。"
                            "拆封本身不等于不能退：拆封查验不影响商品完好即可七天无理由；已使用/影响二次销售才不适用；有质量问题走 P02 十五天路径。"
                            "事实里可能有多个任务结果：必须逐项回答，不能漏；投诉项要说明已转人工，动作项要说明办理结果。"
                            "urgent 为 true 时，要明确说明已加急/优先处理。"
                        )
                    ),
                    HumanMessage(content=f"事实：{context}\n\n用户：{_last_user_text(state['messages'])}"),
                ]
            )
            info["source"] = "llm"
            text = _with_citation(str(msg.content).strip() or template, policy_refs)
            if state.get("urgent") and "加急" not in text:
                text = "已加急处理：" + text
            candidates = ((state.get("tool_result") or {}).get("data") or {}).get("orders") or []
            if len(candidates) == 1 and candidates[0].get("orderNo") and candidates[0]["orderNo"] not in text:
                text = f"已定位到订单 {candidates[0]['orderNo']}。" + text
            # 回复必须写回 messages，否则下一轮上下文里只有用户的话，没有 Agent 的答复
            return {
                "reply": text,
                "messages": [AIMessage(content=text)],
                "reply_chain": "llm",
                "knowledge": knowledge,
                "policy_refs": policy_refs,
            }
        except Exception as exc:  # noqa: BLE001 - 模型不可用仍要能答
            info["source"] = "template"
            info["fallback_reason"] = str(exc)[:200]
            return {
                "reply": template,
                "messages": [AIMessage(content=template)],
                "reply_chain": "template",
                "knowledge": knowledge,
                "policy_refs": policy_refs,
            }
