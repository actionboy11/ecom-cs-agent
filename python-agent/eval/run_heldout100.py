"""100 条 held-out：规则 vs Agent，双 judge（结果导向 + 严格清单），并生成人工抽检清单。"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import subprocess
import time
from pathlib import Path

import httpx

from eval.baseline_rule import reply as baseline_reply
from eval.judge import JudgeUnavailable, judge_reply

HERE = Path(__file__).parent
JAVA = "http://localhost:8080"
AGENT = "http://localhost:8000"
DOCS = HERE.parents[1] / "docs" / "eval"


def load_cases(name: str = "heldout100_cases.jsonl") -> list[dict]:
    return [
        json.loads(line)
        for line in (HERE / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="2026-11-15-heldout100")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--cases", default="heldout100_cases.jsonl")
    parser.add_argument("--reset", action="store_true", help="每条用例前清空售后单，保证独立")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if args.limit:
        cases = cases[: args.limit]

    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        login = await client.post(
            f"{JAVA}/api/auth/login", json={"username": "buyer_a", "password": "demo123"}
        )
        login.raise_for_status()
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        orders = (await client.get(f"{JAVA}/api/orders", headers=headers)).json()

        rows = []
        for index, case in enumerate(cases, start=1):
            if args.reset:
                await asyncio.to_thread(
                    subprocess.run,
                    ["docker", "compose", "exec", "-T", "mysql", "mysql", "-ucsagent", "-pcsagent",
                     "cs_agent", "-e", "DELETE FROM after_sales_requests;"],
                    cwd=str(HERE.parents[1]), capture_output=True, check=False,
                )
            base_reply = baseline_reply(case["input"], orders)
            thread = f"heldout100-{case['id']}-{int(time.time())}"
            resp = await client.post(
                f"{AGENT}/api/v1/chat",
                json={"thread_id": thread, "message": case["input"]},
                headers=headers,
            )
            resp.raise_for_status()
            agent = resp.json()
            if agent.get("pending_actions"):
                confirm = await client.post(
                    f"{AGENT}/api/v1/chat",
                    json={"thread_id": thread, "message": "确认执行"},
                    headers=headers,
                )
                if confirm.status_code == 200:
                    agent = confirm.json()
            rows.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "difficulty": case.get("difficulty"),
                    "order_present": case.get("order_present"),
                    "input": case["input"],
                    "expected": case["expected"],
                    "baseline_reply": base_reply,
                    "agent_reply": agent.get("reply", ""),
                    "agent_intent": agent.get("intent"),
                    "agent_tool": (agent.get("tool_result") or {}).get("tool"),
                    "baseline_solved": None,
                    "agent_solved": None,
                    "baseline_solved_strict": None,
                    "agent_solved_strict": None,
                    "baseline_reason": "",
                    "agent_reason": "",
                    "agent_reason_strict": "",
                }
            )
            print(f"[{index}/{len(cases)}] {case['id']} 跑完", flush=True)

        for index, row in enumerate(rows, start=1):
            for key, reply in (("baseline", row["baseline_reply"]), ("agent", row["agent_reply"])):
                try:
                    result = await judge_reply(row["input"], reply, reference=[row["expected"]])
                    row[f"{key}_solved"] = result.solved
                    row[f"{key}_reason"] = result.reason
                    if key == "baseline":
                        strict = await judge_reply(
                            row["input"], reply, reference=[row["expected"]], rubric="checklist"
                        )
                        row["baseline_solved_strict"] = strict.solved
                    else:
                        strict = await judge_reply(
                            row["input"], reply, reference=[row["expected"]], rubric="checklist"
                        )
                        row["agent_solved_strict"] = strict.solved
                        row["agent_reason_strict"] = strict.reason
                except JudgeUnavailable as exc:
                    row[f"{key}_reason"] = f"judge 失败：{exc}"
            print(f"[judge {index}/{len(rows)}] {row['id']}", flush=True)

    def rate(key: str) -> float | None:
        done = [r for r in rows if r.get(key) is not None]
        return round(sum(1 for r in done if r[key]) / len(done), 3) if done else None

    agreement = round(
        sum(1 for r in rows if r["agent_solved"] == r["agent_solved_strict"])
        / len([r for r in rows if r["agent_solved"] is not None and r["agent_solved_strict"] is not None]),
        3,
    )
    both = round(
        sum(1 for r in rows if r["agent_solved"] and r["agent_solved_strict"])
        / len([r for r in rows if r["agent_solved"] is not None and r["agent_solved_strict"] is not None]),
        3,
    )

    by_category: dict[str, dict] = {}
    for row in rows:
        bucket = by_category.setdefault(
            row["category"],
            {"cases": 0, "baseline": 0, "agent": 0, "agent_strict": 0},
        )
        bucket["cases"] += 1
        bucket["baseline"] += bool(row["baseline_solved"])
        bucket["agent"] += bool(row["agent_solved"])
        bucket["agent_strict"] += bool(row["agent_solved_strict"])

    summary = {
        "cases": len(rows),
        "baseline_rate": rate("baseline_solved"),
        "agent_rate": rate("agent_solved"),
        "baseline_strict_rate": rate("baseline_solved_strict"),
        "agent_strict_rate": rate("agent_solved_strict"),
        "agent_both_rate": both,
        "judge_agreement": agreement,
        "by_category": by_category,
        "rows": rows,
    }
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / f"{args.out}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in (
        "cases", "baseline_rate", "agent_rate", "agent_strict_rate", "agent_both_rate",
        "judge_agreement")}, ensure_ascii=False))

    # 人工抽检：失败 8 + judge 分歧 6 + 随机通过 6
    failures = [r for r in rows if not (r["agent_solved"] and r["agent_solved_strict"])]
    disagreements = [r for r in rows if r["agent_solved"] != r["agent_solved_strict"]]
    solved = [r for r in rows if r["agent_solved"] and r["agent_solved_strict"]]
    rng = random.Random(42)
    sample: list[dict] = []
    for pool, count in ((failures, 8), (disagreements, 6), (solved, 6)):
        candidates = [r for r in pool if r not in sample]
        sample.extend(rng.sample(candidates, min(count, len(candidates))))
    sample = sample[:20]

    lines = [
        f"# 人工抽检（{len(sample)} 条）",
        "",
        "请逐条看「用户输入 / 期望行为 / Agent 回复」，在最后一列填 `通过` 或 `不通过`。",
        "",
        "| id | 类别 | 输入 | 期望行为 | Agent 回复 | J1/J2 | 人工判定 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in sample:
        reply = row["agent_reply"].replace("|", "／").replace("\n", " ")
        expected = row["expected"].replace("|", "／")
        lines.append(
            f"| {row['id']} | {row['category']} | {row['input']} | {expected} | {reply[:160]} | "
            f"{row['agent_solved']}/{row['agent_solved_strict']} |  |"
        )
    (DOCS / f"{args.out}-human-review.md").write_text("\n".join(lines), encoding="utf-8")
    (DOCS / f"{args.out}-human-review.json").write_text(
        json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = [
        f"# 100 条 held-out（{time.strftime('%Y-%m-%d')}）",
        "",
        f"- 规则基线：{summary['baseline_rate']}",
        f"- Agent（结果 judge）：{summary['agent_rate']}",
        f"- Agent（严格清单 judge）：{summary['agent_strict_rate']}",
        f"- Agent 双 judge 同时通过：{summary['agent_both_rate']}",
        f"- 双 judge 一致率：{summary['judge_agreement']}",
        "",
        "| 类别 | 用例 | 规则 | Agent | Agent 严格 |",
        "|---|---|---|---|---|",
    ]
    for category, bucket in by_category.items():
        report.append(
            f"| {category} | {bucket['cases']} | {bucket['baseline']} | "
            f"{bucket['agent']} | {bucket['agent_strict']} |"
        )
    (DOCS / f"{args.out}.md").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
