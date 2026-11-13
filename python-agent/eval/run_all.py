"""三层评测一键跑：标准（等效用例）/ 业务 / 安全（越权 + 拒答）。

报告默认写到 eval/reports/；加 `--out-dir docs/eval` 可生成可提交的基线。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from app.config import settings
from app.graph.builder import build_graph
from app.tools import business_api
from eval.run_eval import REPORT_DIR, apply_judge, load_cases, login, run_case, summarize
from eval.security_check import check as security_check

LAYERS = (
    ("standard", "eval/standard_cases.jsonl", 100),
    ("business", "eval/business_cases.jsonl", None),
    ("safety", "eval/safety_cases.jsonl", None),
)


async def run_layer(
    graph, path: Path, token: str, limit: int | None, split: str, holdout: float
) -> dict:
    cases = load_cases(path, limit, split, holdout)
    for case in cases:
        case.setdefault("provenance", "self-built")
    rows = [await run_case(graph, case, token) for case in cases]
    return {"summary": summarize(rows), "rows": rows, "cases": cases}


def write_combined(
    results: dict[str, dict], security: dict | None, backend_ok: bool,
    split: str, holdout: float, out_dir: Path, name: str,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    lines = [
        f"# 三层评测报告 {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        f"- 后端可用：{'是' if backend_ok else '否（工具类用例会失败）'}",
        f"- 模型：{settings.model_reasoning}；无 Key 时整场走模板（chain=template）",
        f"- 切分：{split}" + (f"（holdout={holdout}）" if split != "all" else ""),
        "- 数据许可：**无**——公开 600 条基准未随仓库分发；standard 层为本地等效用例",
        "",
        "| 层 | 用例 | 数据来源 | 链路 | 意图 | 工具 | 回复 | 平均耗时 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name_, meta in results.items():
        summary = meta["summary"]
        provenance = sorted({str(c.get("provenance", "?")) for c in meta["cases"]}) or ["?"]
        chains = Counter(row.get("chain", "?") for row in meta["rows"])
        lines.append(
            f"| {name_} | {summary['cases']} | {'/'.join(provenance)} | "
            f"{'/'.join(f'{k}×{v}' for k, v in chains.items())} | "
            f"{summary['intent_accuracy']:.1%} | {summary['tool_success']:.1%} | "
            f"{summary['reply_conformance']:.1%} | {summary['avg_latency_ms']} ms |"
        )
    if security is not None:
        lines.append(
            f"| security | {security['cases']} | local | llm/template | — | "
            f"拦截 {security['blocked']}/{security['cases']} | — | — |"
        )
    lines += ["", "## 说明", ""]
    lines.append(
        "- standard 层是等效用例，指标为「回复符合率」代理，不是 SPEC 的任务完成率/oracle 轨迹比对；"
        "公开集接入见 `eval/public_bench.py`。"
    )
    lines.append(
        f"- security 层：4 条越权，新增 DENIED 审计覆盖 {security['denied_audits'] if security else 0} 个目标资源。"
    )
    business = results.get("business", {}).get("summary", {})
    if business.get("judge_rate") is not None:
        lines.append(
            f"- business 第二轨（judge）：{business['judge_rate']:.1%}"
            f"（{business['judge_resolved']}/{business['judge_cases']}），"
            f"失败 {business.get('judge_failed', 0)}，模板跳过 {business.get('judge_skipped_template', 0)}"
        )
    lines += ["", "## 引用命中", ""]
    for name_, meta in results.items():
        summary = meta["summary"]
        if summary.get("citation_hit_rate") is None:
            continue
        lines.append(f"- {name_}：回答 {summary['citation_hit_rate']:.1%}，检索 {summary['retrieval_hit_rate']:.1%}")
    lines += ["", "## 拒答分类", ""]
    for category, bucket in (results.get("safety", {}).get("summary", {}).get("safety_by_category") or {}).items():
        lines.append(f"- {category}：{bucket['passed']}/{bucket['cases']}")
    lines += ["", "## 失败用例", ""]
    for name_, meta in results.items():
        for row in meta["rows"]:
            if not (row["intent_ok"] and row["tool_ok"] and row["reply_ok"]):
                lines.append(f"- [{name_}] {row['id']} `{row['input'][:20]}` → {row['reply'][:80]}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


async def main() -> None:
    parser = argparse.ArgumentParser(description="三层评测（含安全层）")
    parser.add_argument("--standard-limit", type=int, default=100, help="标准层抽样条数")
    parser.add_argument("--split", choices=["all", "train", "holdout"], default="all")
    parser.add_argument("--holdout", type=float, default=0.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out-dir", default=None, help="报告目录（默认 eval/reports）")
    parser.add_argument("--name", default=None, help="报告文件名")
    parser.add_argument("--judge", action="store_true", help="业务层启用 LLM judge 第二轨")
    parser.add_argument("--judge-limit", type=int, default=0, help="judge 抽样条数（0=全量）")
    args = parser.parse_args()

    backend_ok = await business_api.healthy()
    token = await login("buyer_a") if backend_ok else ""
    graph = build_graph(MemorySaver())

    results: dict[str, dict] = {}
    for layer, path, default_limit in LAYERS:
        limit = args.standard_limit if layer == "standard" else default_limit
        results[layer] = await run_layer(graph, Path(path), token, limit, args.split, args.holdout)

    security = await security_check() if backend_ok else None

    if args.judge:
        business = results["business"]
        business["summary"].update(
            await apply_judge(business["rows"], business["cases"], limit=args.judge_limit)
        )
        if business["summary"].get("judge_cases"):
            business["summary"]["judge_model"] = settings.model_reasoning

    if args.json:
        payload = {name: r["summary"] for name, r in results.items()}
        if security is not None:
            payload["security"] = security
        print(json.dumps(payload, ensure_ascii=False))
    else:
        out_dir = Path(args.out_dir) if args.out_dir else REPORT_DIR
        name = args.name or f"three-layers-{time.strftime('%Y%m%d-%H%M%S')}.md"
        report = write_combined(results, security, backend_ok, args.split, args.holdout, out_dir, name)
        print(f"报告：{report}")
        for layer, r in results.items():
            print(layer, json.dumps(r["summary"], ensure_ascii=False))
        if security is not None:
            print("security", json.dumps(security, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
