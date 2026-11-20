"""政策咨询与人工升级：只回答，不建单；不主动 handoff，除明确要求/赔偿损失。"""

from __future__ import annotations

from app.graph.decision import Decision

PRICE_WORDS = ("价保", "补差价", "降价", "退差")
TRADE_IN_WORDS = ("以旧换新", "旧机", "折价换")
PHONE_WORDS = ("客服电话", "电话多少", "人工电话")
EXPLICIT_HANDOFF_WORDS = ("转人工", "人工客服", "找人工", "投诉", "曝光", "12315")
COMPENSATION_WORDS = (
    "赔偿", "赔钱", "赔我", "能赔", "索赔", "损失",
    "弄湿", "泡了", "泡坏", "电脑坏了", "赔吗",
)


def detect(text: str) -> Decision | None:
    if any(word in text for word in COMPENSATION_WORDS):
        return Decision(
            kind="handoff",
            reason="compensation_or_damage",
            text="这类赔偿或物品损失需要人工核实责任与金额，已为您转接人工。",
        )

    if any(word in text for word in EXPLICIT_HANDOFF_WORDS):
        return Decision(
            kind="handoff",
            reason="explicit_human_request",
            text="已按您的要求转接人工客服。",
        )

    if any(word in text for word in TRADE_IN_WORDS):
        return Decision(
            kind="answer",
            text=(
                "目前售后政策没有“以旧换新/旧机折价抵扣”这项服务。"
                "支持的是同订单商品的常规换货：需先寄回原商品，仓库质检通过后再寄出；"
                "具体是否符合换货条件，要看订单状态和签收时间。"
            ),
        )

    if any(word in text for word in PRICE_WORDS):
        return Decision(
            kind="answer",
            text=(
                "价保规则：同商品同规格在签收后 15 日内降价，可申请退差；"
                "限时秒杀、直播间专享价、优惠券叠加、赠品变动不参与。"
                "超过 15 日的价格变化不在价保范围内。"
            ),
        )

    if any(word in text for word in PHONE_WORDS):
        return Decision(
            kind="answer",
            text=(
                "平台没有公开的售后电话；可以在订单页使用在线客服，"
                "或继续在这里留言，我会按订单和问题帮您处理。"
            ),
        )

    return None
