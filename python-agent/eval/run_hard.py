"""AI 增量对照实验：规则基线 vs Agent，同一套「AI-only」难题，judge 判解决。

用法（仓库根目录）：
    python -m eval.run_hard

需要：Java/Agent 在线、模型 Key 可用（judge 用 reasoning 模型）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx

from eval.baseline_rule import reply as baseline_reply
from eval.judge import JudgeUnavailable, judge_reply

HERE = Path(__file__).parent
JAVA = "http://localhost:8080"
AGENT = "http://localhost:8000"
REPORT_DIR = HERE / "reports"
DOCS = HERE.parents[1] / "docs" / "eval"


def load_cases() -> list[dict]:
    return [
        json.loads(line)
        for line in (HERE / "hard_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def main() -> None:
    parser = argparse.ArgumentParser(description="规则基线 vs Agent")
    parser.add_argument("--out", default="2026-11-15-hard-baseline")
    parser.add_argument("--skip-judge", action="store_true")
    args = parser.parse_args()

    cases = load_cases()
    async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
        login = await client.post(
            f"{JAVA}/api/auth/login", json={"username": "buyer_a", "password": "demo123"}
        )
        login.raise_for_status()
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        orders_resp = await client.get(f"{JAVA}/api/orders", headers=headers)
        orders_resp.raise_for_status()
        orders = orders_resp.json()

        rows = []
        for case in cases:
            base_reply = baseline_reply(case["input"], orders)
            agent_resp = await client.post(
                f"{AGENT}/api/v1/chat",
                json={"thread_id": f"hard-{case['id']}-{int(time.time())}", "message": case["input"]},
                headers=headers,
            )
            agent_resp.raise_for_status()
            agent_data = agent_resp.json()
            row = {
                "id": case["id"],
                "category": case["category"],
                "input": case["input"],
                "expected": case["expected"],
                "baseline_reply": base_reply,
                "agent_reply": agent_data.get("reply", ""),
                "agent_intent": agent_data.get("intent"),
                "agent_tools": (agent_data.get("tool_result") or {}).get("tool"),
                "agent_refs": agent_data.get("policy_refs") or [],
                "baseline_solved": None,
                "agent_solved": None,
                "baseline_reason": "",
                "agent_reason": "",
            }
            rows.append(row)
            print(f"[{case['id']}] 跑完")

    if not args.skip_judge:
        for row in rows:
            for key, reply in (("baseline", row["baseline_reply"]), ("agent", row["agent_reply"])):
                try:
                    result = await judge_reply(
                        row["input"], reply, reference=[row["expected"]]
                    )
                    row[f"{key}_solved"] = result.solved
                    row[f"{key}_reason"] = result.reason
                except JudgeUnavailable as exc:
                    row[f"{key}_reason"] = f"judge 失败：{exc}"
                    print(f"[{row['id']}] {key} judge 失败：{exc}")

    def rate(key: str) -> float | None:
        done = [r for r in rows if r.get(f"{key}_solved") is not None]
        if not done:
            return None
        return round(sum(1 for r in done if r[f"{key}_solved"]) / len(done), 3)

    by_category: dict[str, dict] = {}
    for row in rows:
        bucket = by_category.setdefault(
            row["category"], {"cases": 0, "baseline": 0, "agent": 0}
        )
        bucket["cases"] += 1
        if row["baseline_solved"]:
            bucket["baseline"] += 1
        if row["agent_solved"]:
            bucket["agent"] += 1

    summary = {
        "cases": len(rows),
        "baseline_rate": rate("baseline"),
        "agent_rate": rate("agent"),
        "delta": (
            round(rate("agent") - rate("baseline"), 3)
            if rate("agent") is not None and rate("baseline") is not None
            else None
        ),
        "by_category": by_category,
        "rows": rows,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f"{args.out}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / f"{args.out}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in ("cases", "baseline_rate", "agent_rate", "delta")}, ensure_ascii=False))

    lines = [
        f"# AI 增量对照：规则基线 vs Agent（{time.strftime('%Y-%m-%d')}）",
        "",
        f"- 用例：{summary['cases']} 条（AI-only 难题集）",
        f"- 规则基线解决率：{summary['baseline_rate']}",
        f"- Agent 解决率：{summary['agent_rate']}",
        f"- 增量：{summary['delta']}",
        "",
        "| 类别 | 用例 | 规则基线 | Agent |",
        "|---|---|---|---|",
    ]
    for category, bucket in by_category.items():
        lines.append(
            f"| {category} | {bucket['cases']} | {bucket['baseline']}/{bucket['cases']} | {bucket['agent']}/{bucket['cases']} |"
        )
    lines += ["", "## 逐题对照", "", "| id | 输入 | 规则 | Agent | 规则理由 / Agent 理由 |", "|---|---|---|---|---|"]
    for row in rows:
        mark = lambda v: "✓" if v else ("—" if v is None else "✗")
        reason = f"{row['baseline_reason'][:60]} / {row['agent_reason'][:60]}"
        lines.append(
            f"| {row['id']} | {row['input'][:22]} | {mark(row['baseline_solved'])} | "
            f"{mark(row['agent_solved'])} | {reason} |"
        )
    lines += ["", "## 说明", "", "- 规则基线只做关键词、正则、固定话术，不拆多意图、不做例外推理", "- judge 用 reasoning 模型判「是否解决」，两列都标注理由"]
    (DOCS / f"{args.out}.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
