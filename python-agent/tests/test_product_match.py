from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.nlp.product_match import match_products

CASES = Path(__file__).resolve().parents[1] / "eval/product_match_cases.jsonl"


def _cases():
    return [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("case", _cases(), ids=lambda item: item["id"])
def test_contract_cases(case: dict) -> None:
    actual = match_products(case["input"])
    expected = case["expected"]
    assert [(m["canonical"], m["span"]) for m in actual["matches"]] == [
        (m["canonical"], m["span"]) for m in expected["matches"]
    ]
    assert [(u["surface"], u["span"]) for u in actual["unknown"]] == [
        (u["surface"], u["span"]) for u in expected["unknown"]
    ]


def test_compound_does_not_swallow_product() -> None:
    result = match_products("耳机套")
    assert result["matches"] == []
    assert result["unknown"][0]["surface"] == "耳机套"


def test_false_positive_is_rejected() -> None:
    result = match_products("女儿机会")
    assert result["matches"] == []
    assert result["unknown"] == []
