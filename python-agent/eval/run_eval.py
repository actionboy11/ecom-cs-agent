"""评测入口：跑 cases.jsonl，产出指标报告。

用法：
    uv run python eval/run_eval.py
    uv run python eval/run_eval.py --limit 5 --no-llm

指标口径（写简历时会用到）：
- intent_accuracy   意图是否判对
- tool_success      该调工具的 case 是否成功拿到数据
- reply_conformance 回复是否包含必须信息（规则判定，非主观打分）
- handoff_rate      投诉 case 是否走到人工
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.graph.builder import build_graph
from app.tools import business_api

try:  # 作为包导入（pytest / python -m eval.run_eval）
    from eval.metrics import citation_stats, extract_citations
except ImportError:  # 作为脚本运行（python eval/run_eval.py）
    from metrics import citation_stats, extract_citations

HERE = Path(__file__).parent
REPORT_DIR = HERE / "reports"


def load_cases(path: Path, limit: int | None = None, split: str = "all", holdout: float = 0.0) -> list[dict]:
    """读取用例。

    ``holdout`` 用固定规则切分（每 5 条取 1 条作 holdout），保证可复现，
    也保证「调优用的集」和「验收用的集」不是同一批——避免自己考自己。
    """
    raw = path.read_text(encoding="utf-8-sig")  # utf-8-sig：容忍 Windows 编辑器写入的 BOM
    cases = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if holdout > 0:
        step = max(int(round(1 / holdout)), 2)
        if split == "holdout":
            cases = [c for i, c in enumerate(cases) if i % step == 0]
        elif split == "train":
            cases = [c for i, c in enumerate(cases) if i % step != 0]
    return cases[:limit] if limit else cases


async def run_case(graph, case: dict) -> dict:
    thread_id = f"eval-{case['id']}-{int(time.time() * 1000)}"
    started = time.perf_counter()
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=case["input"])], "thread_id": thread_id},
        {"configurable": {"thread_id": thread_id}},
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)

    intent = result.get("intent")
    tool_result = result.get("tool_result") or {}
    reply = result.get("reply") or ""
    interrupt = result.get("__interrupt__") or ()

    tool_ok = True
    if case.get("expect_tool"):
        tool_ok = bool(tool_result) and not tool_result.get("error")
    conformance = all(token in reply for token in case.get("must_contain", []))

    # 引用命中：状态里的主引用 + 回复正文里出现的编号，取并集
    citations = list(dict.fromkeys((result.get("policy_refs") or []) + extract_citations(reply)))
    expected = case.get("expect_citation")

    return {
        "id": case["id"],
        "input": case["input"],
        "intent": intent,
        "intent_ok": intent == case["expect_intent"],
        "tool_ok": tool_ok,
        "reply": reply[:200],
        "reply_ok": conformance,
        "citations": citations,
        "citation_expected": expected,
        "citation_ok": (expected in citations) if expected else None,
        "handoff": bool(interrupt),
        "elapsed_ms": elapsed_ms,
    }


def summarize(rows: list[dict]) -> dict:
    n = max(len(rows), 1)
    summary = {
        "cases": len(rows),
        "intent_accuracy": round(sum(r["intent_ok"] for r in rows) / n, 3),
        "tool_success": round(sum(r["tool_ok"] for r in rows) / n, 3),
        "reply_conformance": round(sum(r["reply_ok"] for r in rows) / n, 3),
        "avg_latency_ms": round(sum(r["elapsed_ms"] for r in rows) / n, 1),
        "handoff_cases": sum(r["handoff"] for r in rows),
    }
    summary.update(citation_stats(rows))
    return summary


def write_report(summary: dict, rows: list[dict], backend_ok: bool) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = REPORT_DIR / f"report-{ts}.md"

    lines = [
        f"# 评测报告 {ts}",
        "",
        f"- 后端业务系统可用：{'是' if backend_ok else '否（工具类 case 会失败）'}",
        f"- case 数：{summary['cases']}",
        f"- 意图准确率：{summary['intent_accuracy']:.1%}",
        f"- 工具成功率：{summary['tool_success']:.1%}",
        f"- 回复符合率：{summary['reply_conformance']:.1%}",
        f"- 引用命中率："
        + (
            f"{summary['citation_hit_rate']:.1%}（{summary['citation_hits']}/{summary['citation_cases']}）"
            if summary.get("citation_hit_rate") is not None
            else "无标注用例"
        ),
        f"- 平均耗时：{summary['avg_latency_ms']} ms",
        "",
        "| id | 输入 | 意图 | 意图✓ | 工具✓ | 回复✓ | 引用 | 转人工 | 耗时ms |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        cite = r.get("citation_expected") or ""
        if r.get("citation_ok") is False:
            cite = f"✗ 期望{cite} 实际{'/'.join(r.get('citations') or []) or '无'}"
        elif r.get("citation_ok") is True:
            cite = f"✓ {cite}"
        lines.append(
            f"| {r['id']} | {r['input'][:18]} | {r['intent']} | "
            f"{'✓' if r['intent_ok'] else '✗'} | {'✓' if r['tool_ok'] else '✗'} | "
            f"{'✓' if r['reply_ok'] else '✗'} | {cite} | "
            f"{'是' if r['handoff'] else ''} | {r['elapsed_ms']} |"
        )
    lines += ["", "## 引用错例", ""]
    mismatches = summary.get("citation_mismatches") or []
    if mismatches:
        for m in mismatches:
            lines.append(f"- **{m['id']}** 期望 `{m['expected']}`，实际 `{'/'.join(m['actual']) or '无'}`")
    else:
        lines.append("- 无")
    lines += ["", "## 失败 case 原文", ""]
    for r in rows:
        if not (r["intent_ok"] and r["tool_ok"] and r["reply_ok"]):
            lines.append(f"- **{r['id']}** `{r['input']}` → 回复：{r['reply'] or '（空）'}")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(HERE / "cases.jsonl"), help="用例文件路径")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--split", choices=["all", "train", "holdout"], default="all")
    parser.add_argument("--holdout", type=float, default=0.0, help="holdout 比例，如 0.2")
    parser.add_argument("--json", action="store_true", help="只输出 JSON 汇总")
    args = parser.parse_args()

    if args.split != "all" and args.holdout <= 0:
        parser.error("--split train/holdout 需要同时给 --holdout")

    cases = load_cases(Path(args.cases), args.limit, args.split, args.holdout)
    backend_ok = await business_api.healthy()
    # 评测是批处理：用内存 checkpointer，避免把评测会话写进生产状态库
    graph = build_graph(MemorySaver())

    rows = []
    for case in cases:
        row = await run_case(graph, case)
        rows.append(row)
        print(f"[{row['id']}] intent={row['intent']} intent_ok={row['intent_ok']} tool_ok={row['tool_ok']}")

    summary = summarize(rows)
    summary["split"] = args.split
    summary["cases_file"] = Path(args.cases).name
    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        report = write_report(summary, rows, backend_ok)
        print("\n=== 汇总 ===")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"报告：{report}")


if __name__ == "__main__":
    asyncio.run(main())
