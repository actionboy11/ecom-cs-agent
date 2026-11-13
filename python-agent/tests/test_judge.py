"""P1-4：LLM judge 第二轨。"""

from __future__ import annotations

import pytest

from app.config import settings
from eval.judge import (
    JudgeUnavailable,
    aggregate,
    build_prompt,
    judge_reply,
    parse_judgement,
)


def test_build_prompt_includes_reference_points() -> None:
    prompt = build_prompt("退货几天", "7 天", ["7 天", "不影响二次销售"])
    assert "退货几天" in prompt
    assert "7 天；不影响二次销售" in prompt


def test_parse_strict_json() -> None:
    result = parse_judgement('{"resolved": true, "reason": "要点齐全"}')
    assert result.resolved is True
    assert result.reason == "要点齐全"


def test_parse_fenced_json() -> None:
    raw = '```json\n{"resolved": false, "reason": "答非所问"}\n```'
    assert parse_judgement(raw).resolved is False


def test_parse_regex_fallback() -> None:
    result = parse_judgement('结论：{"resolved": false} 因为缺少订单号')
    assert result.resolved is False


def test_parse_unparseable_raises() -> None:
    with pytest.raises(JudgeUnavailable):
        parse_judgement("我觉得还行")


@pytest.mark.asyncio
async def test_judge_reply_uses_injected_invoke() -> None:
    seen = {}

    async def fake_invoke(prompt: str) -> str:
        seen["prompt"] = prompt
        return '{"resolved": true, "reason": "已解决"}'

    result = await judge_reply("订单到哪了", "运输中", ["运输中"], invoke=fake_invoke)

    assert result.resolved is True
    assert "订单到哪了" in seen["prompt"]


@pytest.mark.asyncio
async def test_judge_unavailable_without_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "qwen_api_key", "")

    with pytest.raises(JudgeUnavailable):
        await judge_reply("问题", "回复")


def test_aggregate_rate() -> None:
    from eval.judge import JudgeResult

    stats = aggregate([JudgeResult(True, ""), JudgeResult(False, ""), JudgeResult(True, "")])
    assert stats == {"judge_cases": 3, "judge_resolved": 2, "judge_rate": 0.667}
