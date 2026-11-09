"""S4-2：引用命中率。"""

from __future__ import annotations

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
        "citation_expected": "P01",
        "citation_ok": True,
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
        "citations": ["P02"],
        "citation_expected": "P03",
        "citation_ok": False,
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
        "citation_expected": None,
        "citation_ok": None,
    },
]


def test_extract_citations_dedupes_in_order() -> None:
    assert extract_citations("依据：[P03]、[P01]，又见 [P03]") == ["P03", "P01"]
    assert extract_citations("没有引用") == []


def test_citation_stats_counts_only_annotated_cases() -> None:
    stats = citation_stats(ROWS)
    assert stats["citation_cases"] == 2
    assert stats["citation_hits"] == 1
    assert stats["citation_hit_rate"] == 0.5
    assert stats["citation_mismatches"] == [{"id": "b36", "expected": "P03", "actual": ["P02"]}]


def test_citation_stats_without_annotations_is_none() -> None:
    stats = citation_stats([ROWS[2]])
    assert stats["citation_cases"] == 0
    assert stats["citation_hit_rate"] is None


def test_summarize_includes_citation_metrics() -> None:
    summary = summarize(ROWS)
    assert summary["citation_hit_rate"] == 0.5
    assert summary["citation_mismatches"][0]["id"] == "b36"


def test_report_prints_mismatch_expectation(tmp_path, monkeypatch) -> None:
    import eval.run_eval as run_eval

    monkeypatch.setattr(run_eval, "REPORT_DIR", tmp_path)
    path = write_report(summarize(ROWS), ROWS, backend_ok=True)
    text = path.read_text(encoding="utf-8")

    assert "引用命中率：50.0%（1/2）" in text
    assert "期望 `P03`，实际 `P02`" in text
