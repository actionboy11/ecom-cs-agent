"""S6-2：三层评测的用例生成与适配。"""

from __future__ import annotations

import json
from pathlib import Path

from eval.gen_standard_cases import generate
from eval.public_bench import adapt, guess_intent
from eval.security_check import TARGETS, evaluate


def test_standard_cases_are_deterministic_and_layered() -> None:
    first = generate()
    second = generate()
    assert first == second
    assert len(first) == 600
    intents = {case["expect_intent"] for case in first}
    assert intents == {"order_query", "logistics", "refund", "policy", "product_info"}
    assert all(case["provenance"] == "local-equivalent" for case in first)


def test_committed_standard_cases_match_the_generator() -> None:
    committed = [
        json.loads(line)
        for line in (Path(__file__).resolve().parents[1] / "eval" / "standard_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert committed == generate()


def test_security_evaluate_requires_all_targets_covered() -> None:
    ok = evaluate(4, {"CS2024005", "CS2024006", "CS2024007"}, TARGETS)
    assert ok["ok"] is True
    assert ok["denied_audits"] == 3

    partial = evaluate(4, {"CS2024005"}, TARGETS)
    assert partial["ok"] is False

    not_blocked = evaluate(3, {"CS2024005", "CS2024006", "CS2024007"}, TARGETS)
    assert not_blocked["ok"] is False


def test_public_bench_adapter_maps_question_and_answer() -> None:
    row = adapt({"question": "退款多久到账", "answer": "1-3 个工作日原路退回"}, 1)

    assert row["id"] == "pub-001"
    assert row["input"] == "退款多久到账"
    assert row["provenance"] == "public"
    assert "1-3" in row["must_contain"]


def test_public_bench_guesses_intent_by_keywords() -> None:
    assert guess_intent("退款多久到账") == "refund"
    assert guess_intent("订单 CS2024001") == "order_query"
    assert guess_intent("你好") == "other"

