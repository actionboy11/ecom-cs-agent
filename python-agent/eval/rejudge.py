"""用校准后的 judge 只重判已有 100 条回复（不重跑 Agent），并生成随机人工样本。"""

from __future__ import annotations

import asyncio
import json
import math
import random
from pathlib import Path

from eval.judge import JudgeUnavailable, judge_reply

DOCS = Path(__file__).resolve().parents[2] / "docs" / "eval"
SOURCE = DOCS / "2026-11-15-heldout100.json"
OUT = "2026-11-15-heldout100-calibrated"


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


async def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = data["rows"]

    for index, row in enumerate(rows, start=1):
        try:
            judge1 = await judge_reply(row["input"], row["agent_reply"], reference=[row["expected"]])
            judge2 = await judge_reply(
                row["input"], row["agent_reply"], reference=[row["expected"]], rubric="checklist"
            )
            base = await judge_reply(row["input"], row["baseline_reply"], reference=[row["expected"]])
            row["cal_agent_solved"] = judge1.solved
            row["cal_agent_reason"] = judge1.reason
            row["cal_agent_strict"] = judge2.solved
            row["cal_agent_strict_reason"] = judge2.reason
            row["cal_baseline_solved"] = base.solved
            row["cal_baseline_reason"] = base.reason
        except JudgeUnavailable as exc:
            row["cal_agent_reason"] = f"judge 失败：{exc}"
        print(f"[{index}/{len(rows)}] {row['id']}", flush=True)

    def rate(key: str) -> tuple[float, int, int]:
        done = [r for r in rows if r.get(key) is not None]
        passed = sum(1 for r in done if r[key])
        return (round(passed / len(done), 3) if done else 0.0, passed, len(done))

    agent_rate, agent_n, total = rate("cal_agent_solved")
    strict_rate, strict_n, _ = rate("cal_agent_strict")
    base_rate, base_n, _ = rate("cal_baseline_solved")
    both = sum(1 for r in rows if r.get("cal_agent_solved") and r.get("cal_agent_strict"))
    agreement = sum(1 for r in rows if r.get("cal_agent_solved") == r.get("cal_agent_strict"))
    judged = sum(1 for r in rows if r.get("cal_agent_solved") is not None and r.get("cal_agent_strict") is not None)

    by_category: dict[str, dict] = {}
    for row in rows:
        bucket = by_category.setdefault(row["category"], {"cases": 0, "base": 0, "agent": 0, "strict": 0})
        bucket["cases"] += 1
        bucket["base"] += bool(row.get("cal_baseline_solved"))
        bucket["agent"] += bool(row.get("cal_agent_solved"))
        bucket["strict"] += bool(row.get("cal_agent_strict"))

    failures = [r for r in rows if not r.get("cal_agent_solved")]
    taxonomy = {
        "未定位订单": sum(1 for r in failures if "订单" in r.get("cal_agent_reason", "") and "定位" in r.get("cal_agent_reason", "")),
        "多动作缺失": sum(1 for r in failures if r.get("category") == "多动作"),
        "未说明关键事实": sum(1 for r in failures if "说明" in r.get("cal_agent_reason", "") or "未回答" in r.get("cal_agent_reason", "")),
        "错订单/事实错误": sum(1 for r in failures if "错" in r.get("cal_agent_reason", "")),
        "其他": 0,
    }
    taxonomy["其他"] = len(failures) - sum(v for k, v in taxonomy.items() if k != "其他")

    summary = {
        "cases": len(rows),
        "baseline_rate": base_rate,
        "baseline_ci": wilson(base_n, total),
        "agent_rate": agent_rate,
        "agent_ci": wilson(agent_n, total),
        "agent_strict_rate": strict_rate,
        "agent_strict_ci": wilson(strict_n, total),
        "agent_both_rate": round(both / judged, 3) if judged else 0.0,
        "judge_agreement": round(agreement / judged, 3) if judged else 0.0,
        "delta": round(agent_rate - base_rate, 3),
        "by_category": by_category,
        "failures": len(failures),
        "taxonomy": taxonomy,
        "rows": rows,
    }
    (DOCS / f"{OUT}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("cases", "baseline_rate", "agent_rate", "agent_strict_rate", "delta", "judge_agreement")}, ensure_ascii=False))

    lines = [
        "# 100 条 held-out（校准后 judge，仅重判）",
        "",
        f"- 规则基线：{base_rate:.0%}（95% CI {summary['baseline_ci'][0]:.0%}–{summary['baseline_ci'][1]:.0%}）",
        f"- Agent J1：{agent_rate:.0%}（95% CI {summary['agent_ci'][0]:.0%}–{summary['agent_ci'][1]:.0%}）",
        f"- Agent J2：{strict_rate:.0%}（95% CI {summary['agent_strict_ci'][0]:.0%}–{summary['agent_strict_ci'][1]:.0%}）",
        f"- 双 judge 同时通过：{summary['agent_both_rate']:.0%}",
        f"- 双 judge 一致率：{summary['judge_agreement']:.0%}",
        f"- 相对基线增量：{summary['delta']:+.0%}",
        "",
        "| 类别 | 用例 | 规则 | Agent J1 | Agent J2 |",
        "|---|---|---|---|---|",
    ]
    for category, bucket in by_category.items():
        lines.append(f"| {category} | {bucket['cases']} | {bucket['base']} | {bucket['agent']} | {bucket['strict']} |")
    lines += ["", f"失败 {len(failures)} 条，分类：{taxonomy}"]
    (DOCS / f"{OUT}.md").write_text("\n".join(lines), encoding="utf-8")

    # 随机 30 条人工样本（不是分层，用于估计总体）
    rng = random.Random(2026)
    sample = rng.sample(rows, 30)
    human = [
        "# 随机人工抽检（30 条）",
        "",
        "随机抽取，未按失败分层，用来估计 100 条的总体通过率。最后一列填 `通过` / `不通过`。",
        "",
        "| id | 类别 | 输入 | 期望行为 | Agent 回复 | J1/J2 | 人工判定 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in sample:
        reply = row["agent_reply"].replace("|", "／").replace("\n", " ")
        human.append(
            f"| {row['id']} | {row['category']} | {row['input']} | {row['expected'].replace('|', '／')} | "
            f"{reply[:160]} | {row.get('cal_agent_solved')}/{row.get('cal_agent_strict')} |  |"
        )
    (DOCS / f"{OUT}-random-human.md").write_text("\n".join(human), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
