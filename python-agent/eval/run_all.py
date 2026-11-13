"""三层评测一键跑：标准（等效用例）/ 业务 / 安全，输出合并报告。"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from eval.run_eval import REPORT_DIR, load_cases, login, run_case, summarize
from app.config import settings
from app.graph.builder import build_graph
from app.tools import business_api
from langgraph.checkpoint.memory import MemorySaver

LAYERS = (
    ("standard", "eval/standard_cases.jsonl", "本地等效用例（公开集未分发）"),
    ("business", "eval/business_cases.jsonl", "自建 60 条业务集"),
    ("safety", "eval/safety_cases.jsonl", "拒答四类 9 条"),
)


async def run_layer(graph, path: Path, token: str, limit: int | None) -> dict:
    cases = load_cases(path, limit)
    rows = [await run_case(graph, case, token) for case in cases]
    return {"summary": summarize(rows), "rows": rows}


def write_combined(results: dict[str, dict], backend_ok: bool) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = REPORT_DIR / f"three-layers-{ts}.md"
    lines = [
        f"# 三层评测报告 {ts}",
        "",
        f"- 后端可用：{'是' if backend_ok else '否'}",
        f"- 模型：{settings.model_reasoning}（失败时模板兜底）",
        "",
        "| 层 | 用例 | 意图 | 工具 | 回复 | 引用命中 | 数据来源 |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, _, provenance in LAYERS:
        if name not in results:
            continue
        summary = results[name]["summary"]
        citation = (
            f"{summary['citation_hit_rate']:.1%}" if summary.get("citation_hit_rate") is not None else "—"
        )
        lines.append(
            f"| {name} | {summary['cases']} | {summary['intent_accuracy']:.1%} | "
            f"{summary['tool_success']:.1%} | {summary['reply_conformance']:.1%} | {citation} | {provenance} |"
        )
    lines += ["", "## 拒答分类", ""]
    safety = results.get("safety", {}).get("summary", {})
    for category, bucket in (safety.get("safety_by_category") or {}).items():
        lines.append(f"- {category}：{bucket['passed']}/{bucket['cases']}")
    lines += ["", "## 失败用例", ""]
    for name in results:
        for row in results[name]["rows"]:
            if not (row["intent_ok"] and row["tool_ok"] and row["reply_ok"]):
                lines.append(f"- [{name}] {row['id']} `{row['input'][:20]}` → {row['reply'][:80]}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


async def main() -> None:
    parser = argparse.ArgumentParser(description="三层评测")
    parser.add_argument("--standard-limit", type=int, default=100, help="标准层抽样条数")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    backend_ok = await business_api.healthy()
    token = await login("buyer_a") if backend_ok else ""
    graph = build_graph(MemorySaver())

    results: dict[str, dict] = {}
    for name, path, _ in LAYERS:
        limit = args.standard_limit if name == "standard" else None
        results[name] = await run_layer(graph, Path(path), token, limit)

    if args.json:
        print(json.dumps({name: r["summary"] for name, r in results.items()}, ensure_ascii=False))
    else:
        report = write_combined(results, backend_ok)
        print(f"报告：{report}")
        for name, r in results.items():
            print(name, json.dumps(r["summary"], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
