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
    # 用户内容被包在数据标签里，降低注入风险
    assert "<question>退货几天</question>" in prompt


def test_parse_strict_json() -> None:
    result = parse_judgement('{"solved": true, "reason": "要点齐全"}')
    assert result.solved is True
    assert result.reason == "要点齐全"


def test_parse_accepts_spec_and_legacy_keys() -> None:
    assert parse_judgement('{"resolved": false, "reason": "缺信息"}').solved is False
    assert parse_judgement('{"solved": true}').solved is True


def test_parse_rejects_string_bools_that_are_not_boolean_like() -> None:
    # 旧实现 bool("false") 会变成 True；现在必须显式识别
    assert parse_judgement('{"solved": "false"}').solved is False
    assert parse_judgement('{"solved": "yes"}').solved is True
    with pytest.raises(JudgeUnavailable):
        parse_judgement('{"solved": "maybe"}')


def test_parse_fenced_json() -> None:
    raw = '```json\n{"solved": false, "reason": "答非所问"}\n```'
    assert parse_judgement(raw).solved is False


def test_parse_regex_fallback() -> None:
    result = parse_judgement('结论：{"resolved": false} 因为缺少订单号')
    assert result.solved is False


def test_parse_unparseable_raises() -> None:
    with pytest.raises(JudgeUnavailable):
        parse_judgement("我觉得还行")


@pytest.mark.asyncio
async def test_judge_reply_uses_injected_invoke() -> None:
    seen = {}

    async def fake_invoke(prompt: str) -> str:
        seen["prompt"] = prompt
        return '{"solved": true, "reason": "已解决"}'

    result = await judge_reply("订单到哪了", "运输中", ["运输中"], invoke=fake_invoke)

    assert result.solved is True
    assert "订单到哪了" in seen["prompt"]


@pytest.mark.asyncio
async def test_model_error_becomes_judge_unavailable() -> None:
    async def broken(_prompt: str) -> str:
        raise RuntimeError("401 Unauthorized")

    with pytest.raises(JudgeUnavailable):
        await judge_reply("问题", "回复", invoke=broken)


@pytest.mark.asyncio
async def test_judge_unavailable_without_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "qwen_api_key", "")

    with pytest.raises(JudgeUnavailable):
        await judge_reply("问题", "回复")


def test_aggregate_rate_and_failures() -> None:
    from eval.judge import JudgeResult

    stats = aggregate(
        [JudgeResult(True, ""), JudgeResult(False, ""), JudgeResult(True, "")], failed=2
    )
    assert stats == {
        "judge_cases": 3,
        "judge_resolved": 2,
        "judge_rate": 0.667,
        "judge_failed": 2,
    }


@pytest.mark.asyncio
async def test_apply_judge_skips_template_and_samples(monkeypatch) -> None:
    from eval import run_eval
    from eval.judge import JudgeResult

    rows = [
        {"id": f"b{i:02d}", "input": "问题", "reply": "回复", "reply_full": "完整回复", "chain": "llm"}
        for i in range(1, 5)
    ] + [
        {"id": "tpl", "input": "问题", "reply": "模板", "reply_full": "模板", "chain": "template"}
    ]
    cases = [{"id": f"b{i:02d}", "must_contain": ["x"]} for i in range(1, 5)]

    async def fake_judge(*_a, **_k):
        return JudgeResult(True, "ok")

    monkeypatch.setattr(run_eval, "judge_reply", fake_judge)

    updates = await run_eval.apply_judge(rows, cases, limit=2, seed=0)

    assert updates["judge_cases"] == 2
    assert updates["judge_skipped_template"] == 1
    assert len(updates["judge_details"]) == 2
    assert sum(1 for r in rows if "judge" in r) == 2


def test_report_escapes_pipe_in_judge_reason(tmp_path) -> None:
    from eval.run_eval import write_report

    rows = [
        {
            "id": "b01",
            "input": "问题",
            "intent": "order_query",
            "intent_ok": True,
            "tool_ok": True,
            "reply_ok": True,
            "reply": "回复",
            "citations": [],
            "policy_refs": [],
            "citation_expected": None,
            "handoff": False,
            "elapsed_ms": 1,
            "judge": {"solved": False, "reason": "a|b\nc"},
        }
    ]
    summary = {
        "cases": 1,
        "intent_accuracy": 1.0,
        "tool_success": 1.0,
        "reply_conformance": 1.0,
        "citation_hit_rate": None,
        "retrieval_hit_rate": None,
        "avg_latency_ms": 1.0,
        "judge_rate": 0.0,
        "judge_resolved": 0,
        "judge_cases": 1,
        "judge_model": "test-model",
        "judge_skipped_template": 0,
        "judge_failed": 0,
    }
    path = write_report(summary, rows, backend_ok=True, report_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "a\\|b" in text
    assert "a|b" not in text

