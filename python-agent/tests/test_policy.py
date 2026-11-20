from __future__ import annotations

from app.graph import policy


def test_price_trade_in_phone_are_answers() -> None:
    for text in ("耳机降价了能补差价吗", "支持以旧换新吗", "客服电话多少"):
        decision = policy.detect(text)
        assert decision is not None
        assert decision.kind == "answer"
        assert decision.text


def test_compensation_and_damage_are_handoff() -> None:
    for text in ("背带断了能赔吗", "杯子漏水把电脑弄湿了"):
        decision = policy.detect(text)
        assert decision is not None
        assert decision.kind == "handoff"


def test_explicit_human_request_is_handoff() -> None:
    decision = policy.detect("给我转人工")
    assert decision is not None
    assert decision.kind == "handoff"
