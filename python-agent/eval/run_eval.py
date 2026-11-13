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
import random
import time
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.config import settings
from app.graph.builder import build_graph
from app.tools import business_api
from eval.judge import JudgeUnavailable, aggregate, judge_reply
from eval.metrics import citation_stats, extract_citations, is_citation_hit

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
        step = max(round(1 / holdout), 2)
        if split == "holdout":
            cases = [c for i, c in enumerate(cases) if i % step == 0]
        elif split == "train":
            cases = [c for i, c in enumerate(cases) if i % step != 0]
    return cases[:limit] if limit else cases


async def login(username: str, password: str = "demo123") -> str:
    """评测用固定账号登录，拿 JWT 注入每次对话（MCP 工具需要）。"""
    import httpx

    from app.config import settings

    try:
        async with httpx.AsyncClient(
            base_url=settings.business_api_base, timeout=5, trust_env=False
        ) as client:
            resp = await client.post(
                "/api/auth/login", json={"username": username, "password": password}
            )
            resp.raise_for_status()
            return str(resp.json().get("token", ""))
    except Exception as exc:  # noqa: BLE001 - 登录失败时工具类用例会明确报 UNAUTHORIZED
        print(f"[warn] 登录失败，工具类用例将失败: {exc}")
        return ""


async def run_case(graph, case: dict, token: str = "") -> dict:
    thread_id = f"eval-{case['id']}-{int(time.time() * 1000)}"
    started = time.perf_counter()
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=case["input"])], "thread_id": thread_id},
        {"configurable": {"thread_id": thread_id, "auth_token": token}},
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

    # 回答引用只从回复正文里取；检索主依据单独记录，避免把「检索到了」算成「回答引用了」
    citations = extract_citations(reply)
    retrieved = list(result.get("policy_refs") or [])
    expected = case.get("expect_citation")
    # 报告必须能区分「模型生成」与「模板兜底」：没有 Key 时整场都是兜底链路
    chain = "llm" if settings.deepseek_api_key else "template"

    return {
        "id": case["id"],
        "input": case["input"],
        "intent": intent,
        "intent_ok": intent == case["expect_intent"],
        "tool_ok": tool_ok,
        "reply": reply[:200],
        # judge 必须看完整回复；截断版本只用于报告展示
        "reply_full": reply,
        "reply_ok": conformance,
        "citations": citations,
        "policy_refs": retrieved,
        "citation_expected": expected,
        "safety_category": case.get("safety_category"),
        "chain": chain,
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
    # 拒答按类统计（越权 / 竞品比较 / 无关闲聊 / 违规请求）
    by_category: dict[str, dict[str, int]] = {}
    for row in rows:
        category = row.get("safety_category")
        if not category:
            continue
        bucket = by_category.setdefault(category, {"cases": 0, "passed": 0})
        bucket["cases"] += 1
        bucket["passed"] += 1 if row["reply_ok"] else 0
    if by_category:
        summary["safety_by_category"] = by_category
    return summary


async def apply_judge(
    rows: list[dict], cases: list[dict], limit: int = 0, seed: int = 0
) -> dict:
    """第二轨：只判 LLM 链路的回复（ADR-0003），模板兜底不计入质量。"""
    eligible = [r for r in rows if r.get("chain") == "llm"]
    skipped_template = len(rows) - len(eligible)
    if limit and limit < len(eligible):
        eligible = random.Random(seed).sample(eligible, limit)

    judged: dict[str, object] = {}
    failures: list[str] = []
    for row in eligible:
        reference = next((c.get("must_contain") or [] for c in cases if c["id"] == row["id"]), [])
        context = json.dumps(row.get("tool_result") or {}, ensure_ascii=False)[:800]
        try:
            judged[row["id"]] = await judge_reply(
                row["input"], row.get("reply_full", row["reply"]), reference, context
            )
        except JudgeUnavailable as exc:
            failures.append(f"{row['id']}: {exc}")

    updates = aggregate(list(judged.values()), failed=len(failures))
    updates["judge_skipped_template"] = skipped_template
    if failures:
        updates["judge_failures"] = failures[:5]
    if not judged and failures:
        updates["judge_skipped"] = failures[0]
    details = [
        {"id": rid, "solved": result.solved, "reason": result.reason}
        for rid, result in judged.items()
    ]
    if details:
        updates["judge_details"] = details
        for row in rows:
            if row["id"] in judged:
                result = judged[row["id"]]
                row["judge"] = {"solved": result.solved, "reason": result.reason}
    return updates


def write_report(summary: dict, rows: list[dict], backend_ok: bool, report_dir: Path | None = None) -> Path:
    target = report_dir or REPORT_DIR
    target.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = target / f"report-{ts}.md"

    citation_line = (
        f"{summary['citation_hit_rate']:.1%}（{summary['citation_hits']}/{summary['citation_cases']}）"
        if summary.get("citation_hit_rate") is not None
        else "无标注用例"
    )
    retrieval_line = (
        f"{summary['retrieval_hit_rate']:.1%}（{summary['retrieval_hits']}/{summary['citation_cases']}）"
        if summary.get("retrieval_hit_rate") is not None
        else "无标注用例"
    )

    lines = [
        f"# 评测报告 {ts}",
        "",
        f"- 用例文件：{summary.get('cases_file', '未记录')}",
        f"- 切分：{summary.get('split', 'all')}",
        f"- 后端业务系统可用：{'是' if backend_ok else '否（工具类 case 会失败）'}",
        f"- case 数：{summary['cases']}",
        f"- 意图准确率：{summary['intent_accuracy']:.1%}",
        f"- 工具成功率：{summary['tool_success']:.1%}",
        f"- 回复符合率：{summary['reply_conformance']:.1%}",
        f"- 引用命中率（回答正文）：{citation_line}",
        f"- 检索命中率（主依据）：{retrieval_line}",
        f"- 平均耗时：{summary['avg_latency_ms']} ms",
        "",
        "| id | 输入 | 意图 | 意图✓ | 工具✓ | 回复✓ | 引用 | 转人工 | 耗时ms |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        cite = r.get("citation_expected") or ""
        if r.get("citation_expected") and is_citation_hit(r):
            cite = f"✓ {cite}"
        elif r.get("citation_expected"):
            cite = f"✗ 期望{cite} 实际{'/'.join(r.get('citations') or []) or '无'}"
        lines.append(
            f"| {r['id']} | {r['input'][:18]} | {r['intent']} | "
            f"{'✓' if r['intent_ok'] else '✗'} | {'✓' if r['tool_ok'] else '✗'} | "
            f"{'✓' if r['reply_ok'] else '✗'} | {cite} | "
            f"{'是' if r['handoff'] else ''} | {r['elapsed_ms']} |"
        )
    lines += ["", "## LLM judge（第二轨）", ""]
    if summary.get("judge_rate") is not None:
        lines.append(f"- 模型：{summary.get('judge_model', '?')}")
        lines.append(
            f"- 解决率：{summary['judge_rate']:.1%}（{summary['judge_resolved']}/{summary['judge_cases']}）"
        )
        lines.append(f"- 模板兜底跳过：{summary.get('judge_skipped_template', 0)} 条（ADR-0003）")
        if summary.get("judge_failed"):
            lines.append(f"- 判定失败：{summary['judge_failed']} 条（未计入解决率）")
        lines += ["", "| id | 是否解决 | 理由 |", "|---|---|---|"]
        for r in rows:
            judged = r.get("judge")
            if judged:
                reason = str(judged["reason"]).replace("|", "\\|").replace("\n", " ")
                lines.append(
                    f"| {r['id']} | {'✓' if judged['solved'] else '✗'} | {reason} |"
                )
    elif summary.get("judge_skipped"):
        lines.append(f"- 已跳过：{summary['judge_skipped']}（未配置模型 Key 或输出无法解析）")
    else:
        lines.append("- 未启用（`--judge`）")

    lines += ["", "## 拒答分类统计", ""]
    by_category = summary.get("safety_by_category") or {}
    if by_category:
        for category, bucket in by_category.items():
            lines.append(f"- {category}：{bucket['passed']}/{bucket['cases']}")
    else:
        lines.append("- 无拒答用例")
    lines += ["", "## 引用错例", ""]
    mismatches = summary.get("citation_mismatches") or []
    if mismatches:
        for m in mismatches:
            retrieved = "/".join(m.get("retrieved") or []) or "无"
            lines.append(
                f"- **{m['id']}** 期望 `{m['expected']}`，回答引用 `{'/'.join(m['actual']) or '无'}`，"
                f"检索主依据 `{retrieved}`"
            )
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
    parser.add_argument("--username", default="buyer_a", help="评测登录账号（默认 buyer_a）")
    parser.add_argument("--judge", action="store_true", help="启用 LLM judge 第二轨（需模型 Key，会产生调用）")
    parser.add_argument("--judge-limit", type=int, default=0, help="judge 抽样条数（随机抽样，0 表示全量）")
    parser.add_argument("--judge-seed", type=int, default=0, help="judge 抽样随机种子，保证可复现")
    args = parser.parse_args()

    if args.split != "all" and args.holdout <= 0:
        parser.error("--split train/holdout 需要同时给 --holdout")

    cases = load_cases(Path(args.cases), args.limit, args.split, args.holdout)
    backend_ok = await business_api.healthy()
    token = await login(args.username) if backend_ok else ""
    # 评测是批处理：用内存 checkpointer，避免把评测会话写进生产状态库
    graph = build_graph(MemorySaver())

    rows = []
    for case in cases:
        row = await run_case(graph, case, token)
        rows.append(row)
        if not args.json:
            print(
                f"[{row['id']}] intent={row['intent']} "
                f"intent_ok={row['intent_ok']} tool_ok={row['tool_ok']}"
            )

    summary = summarize(rows)
    summary["split"] = args.split
    summary["cases_file"] = Path(args.cases).name

    if args.judge:
        summary.update(
            await apply_judge(rows, cases, limit=args.judge_limit, seed=args.judge_seed)
        )
        if summary.get("judge_cases"):
            summary["judge_model"] = settings.model_reasoning
        if summary.get("judge_failures"):
            print(f"judge 失败 {summary['judge_failed']} 条：{summary['judge_failures'][0]}")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        report = write_report(summary, rows, backend_ok)
        print("\n=== 汇总 ===")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"报告：{report}")


if __name__ == "__main__":
    asyncio.run(main())
