"""S6-2：三层评测的用例生成与适配。"""

from __future__ import annotations

from eval.gen_standard_cases import generate
from eval.public_bench import adapt, guess_intent


def test_standard_cases_are_deterministic_and_layered() -> None:
    first = generate()
    second = generate()
    assert first == second
    assert len(first) == 600
    intents = {case["expect_intent"] for case in first}
    assert intents == {"order_query", "logistics", "refund", "policy", "product_info"}
    assert all(case["provenance"] == "local-equivalent" for case in first)


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
