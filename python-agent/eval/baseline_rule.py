"""规则基线：模拟一个「做得还不错」的传统售后机器人。

能力边界（尽量公平，不故意做弱）：
- 精确订单号 / 商品关键词匹配订单
- 多个政策关键词可以拼接回答
- 多个订单号可以逐个查状态
- 投诉、加急、结束语有固定话术
做不了：语义指代消解、多动作拆解、政策例外组合推理、自由文本结构化办理。
"""

from __future__ import annotations

import re

ORDER_PATTERN = re.compile(r"(CS\d{7,})", re.IGNORECASE)

PRODUCT_HINTS = {
    "耳机": "耳机",
    "行李箱": "行李箱",
    "杯子": "保温杯",
    "鞋": "跑步鞋",
    "背包": "背包",
    "充电宝": "充电宝",
}

POLICY_LINES = {
    "退货": "七天无理由退货：签收次日起 7 个自然日内，商品完好、不影响二次销售可退；定制类、鲜活易腐、已拆封数字化商品、贴身衣物除外。[P01]",
    "质量问题": "质量问题退换货：签收后 15 天内出现性能故障、破损或与描述不符，可换货或退货退款，需提供图片/视频凭证。[P02]",
    "退款": "退款审核通过后 1-3 个工作日原路退回。[P03]",
    "物流": "物流超过 72 小时无更新可申请催件。[P04]",
    "运费": "退回运费一般由买家承担，质量问题或发错货由商家承担。[P05]",
    "发票": "支持开具电子发票，签收后 30 天内可申请。[P06]",
    "价保": "签收后 15 天内，同商品同平台降价可申请价保，需提供订单号。[P07]",
    "换货": "换货需在签收后 15 天内申请，寄回后 48 小时内发出新品。[P09]",
}

POLICY_KEYWORDS = {
    "退货": ("七天", "无理由", "退货"),
    "质量问题": ("质量问题", "坏了", "漏水", "杂音", "破损"),
    "退款": ("退款", "退钱", "原路"),
    "物流": ("物流", "到哪", "快递", "催"),
    "运费": ("运费", "邮费"),
    "发票": ("发票",),
    "价保": ("价保", "降价", "补差", "差价"),
    "换货": ("换货", "换一码", "换大", "换新"),
}


def _orders_in_text(text: str, orders: list[dict]) -> list[dict]:
    found: list[dict] = []
    for order_no in ORDER_PATTERN.findall(text):
        order_no = order_no.upper()
        match = next((o for o in orders if o.get("orderNo") == order_no), None)
        found.append(match or {"orderNo": order_no, "status": "未知", "itemName": ""})
    return found


def _product_candidates(text: str, orders: list[dict]) -> list[dict]:
    for hint, keyword in PRODUCT_HINTS.items():
        if hint in text:
            return [o for o in orders if keyword in (o.get("itemName") or "")]
    return []


def reply(text: str, orders: list[dict]) -> str:
    if any(word in text for word in ("算了", "不用了", "没事了")):
        return "好的，祝您生活愉快，有需要随时联系。"

    if any(word in text for word in ("投诉", "破服务", "态度", "差评")):
        return "非常抱歉给您带来不好的体验，已记录并转接人工客服优先处理。"

    parts: list[str] = []

    matched_orders = _orders_in_text(text, orders)
    if not matched_orders:
        candidates = _product_candidates(text, orders)
        if len(candidates) == 1:
            matched_orders = candidates
        elif len(candidates) > 1:
            names = "、".join(o["orderNo"] for o in candidates)
            parts.append(f"您有多个相关订单：{names}，请告诉我是哪一单。")

    if matched_orders:
        status = "；".join(
            f"{o['orderNo']} 当前状态：{o.get('status', '未知')}" for o in matched_orders
        )
        parts.append(status)
    elif any(word in text for word in ("那个", "昨天", "上周", "前两天")):
        parts.append("请告诉我是哪一单，或提供订单号。")

    if any(word in text for word in ("很急", "今天必须", "尽快", "马上")):
        parts.append("已为您标记加急，并转接人工优先处理。")

    for topic, words in POLICY_KEYWORDS.items():
        if any(word in text for word in words):
            parts.append(POLICY_LINES[topic])

    if not parts:
        if "处理一下" in text or "帮我处理" in text:
            parts.append("请告诉我是哪一单、遇到什么问题，我帮您处理。")
        else:
            parts.append("请提供订单号或具体问题，我帮您查询。")

    return " ".join(parts)
