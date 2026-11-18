from __future__ import annotations

from app.graph.nodes import _needs_human_handoff


def test_safety_and_dispute_need_handoff() -> None:
    assert _needs_human_handoff("充电宝鼓包了，会不会炸")
    assert _needs_human_handoff("我要赔偿")
    assert _needs_human_handoff("退款被拒了，凭什么")
    assert _needs_human_handoff("东西我留着，钱退我")


def test_normal_return_does_not_need_handoff() -> None:
    assert not _needs_human_handoff("订单 CS2024250 漏水了，我要退货")
    assert not _needs_human_handoff("查一下我的订单")
