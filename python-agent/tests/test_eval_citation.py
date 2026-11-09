"""S4-2：引用命中率。"""

from __future__ import annotations

import json
from pathlib import Path

from eval.metrics import citation_stats, extract_citations
from eval.run_eval import summarize, write_report

ROWS = [
    {
        "id": "b35",
        "intent": "policy",
        "input": "退货政策几天",
        "intent_ok": True,
        "tool_ok": True,
        "reply_ok": True,
        "handoff": False,
        "elapsed_ms": 10.0,
        "citations": ["P01"],
        "policy_refs": ["P01"],
        "citation_expected": "P01",
    },
    {
        "id": "b36",
        "intent": "policy",
        "input": "退款多久到账",
        "intent_ok": True,
        "tool_ok": True,
        "reply_ok": True,
        "handoff": False,
        "elapsed_ms": 12.0,
        "citations": ["P02"],  # 回答引错了
        "policy_refs": ["P03"],  # 但检索是对的
        "citation_expected": "P03",
    },
    {
        "id": "b01",
        "intent": "order_query",
        "input": "查订单",
        "intent_ok": True,
        "tool_ok": True,
        "reply_ok": True,
        "handoff": False,
        "elapsed_ms": 8.0,
        "citations": [],
        "policy_refs": [],
        "citation_expected": None,
    },
]


def test_extract_citations_dedupes_in_order() -> None:
    assert extract_citations("依据：[P03]、[P01]，又见 [P03]") == ["P03", "P01"]
    assert extract_citations("没有引用") == []


def test_citation_stats_separates_answer_from_retrieval() -> None:
    stats = citation_stats(ROWS)
    assert stats["citation_cases"] == 2
    assert stats["citation_hit_rate"] == 0.5  # 回答：1/2
    assert stats["retrieval_hit_rate"] == 1.0  # 检索：2/2
    assert stats["citation_mismatches"] == [
        {"id": "b36", "expected": "P03", "actual": ["P02"], "retrieved": ["P03"]}
    ]


def test_citation_stats_without_annotations_is_none() -> None:
    stats = citation_stats([ROWS[2]])
    assert stats["citation_cases"] == 0
    assert stats["citation_hit_rate"] is None


def test_summarize_includes_citation_metrics() -> None:
    summary = summarize(ROWS)
    assert summary["citation_hit_rate"] == 0.5
    assert summary["retrieval_hit_rate"] == 1.0
    assert summary["citation_mismatches"][0]["id"] == "b36"


def test_report_shows_both_rates_and_actionable_mismatch(tmp_path) -> None:
    path = write_report(summarize(ROWS), ROWS, backend_ok=True, report_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "引用命中率（回答正文）：50.0%（1/2）" in text
    assert "检索命中率（主依据）：100.0%（2/2）" in text
    assert "期望 `P03`，回答引用 `P02`，检索主依据 `P03`" in text


def test_every_policy_case_has_an_expected_citation() -> None:
    """分母以标注为准；凡是 policy 意图的用例都必须标注，否则会从统计里消失。"""
    root = Path(__file__).resolve().parents[1]
    missing = []
    for name in ("business_cases.jsonl", "cases.jsonl"):
        for line in (root / "eval" / name).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            if case.get("expect_intent") == "policy" and not case.get("expect_citation"):
                missing.append(case["id"])
    assert missing == []


def test_with_citation_appends_when_model_omits_it() -> None:
    from app.graph.nodes import _with_citation

    assert _with_citation("退款 1-3 个工作日到账", ["P03"]).endswith("依据：[P03]")
    text = "退款 1-3 个工作日到账 [P03]"
    assert _with_citation(text, ["P03"]) == text
