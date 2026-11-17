"""校验 pilot 题：字段、订单真实性、归属、配额、重复。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "docs/eval/pilot"
CSV_PATH = ROOT / "docs/eval/fixture-orders.csv"

CATEGORIES = {"指代", "多动作", "例外", "动作", "情绪", "边界"}
PERSONAS = {"normal", "urgent", "adversarial"}
EXPECTED_TYPES = {"answer", "clarify", "tool", "confirm", "handoff", "refuse", "handled"}
TOOLS = {
    "find_my_orders", "query_order", "query_logistics", "get_product", "search_policy",
    "create_refund", "create_return", "create_exchange", "urge_logistics",
    "load_skill", "handoff_to_human",
}
FORBIDDEN = {"wrong_order", "write_without_confirm", "leak_other", "fabricate_policy", "unsupported_action"}
WRITER_QUOTAS = {
    "writer-a": {"指代": 3, "多动作": 2, "例外": 2, "动作": 2, "情绪": 1},
    "writer-b": {"指代": 2, "多动作": 2, "例外": 2, "动作": 2, "情绪": 2},
    "writer-c": {"指代": 1, "多动作": 1, "例外": 1, "动作": 2, "边界": 5},
}


def load_orders() -> dict[str, dict[str, dict]]:
    users: dict[str, dict[str, dict]] = {}
    with CSV_PATH.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            users.setdefault(row["user"], {})[row["order_no"]] = row
    return users


def check_case(case: dict, writer: str, users: dict[str, dict[str, dict]], seen_inputs: set[str]) -> list[str]:
    errors: list[str] = []
    required = {"id", "category", "persona", "input", "preconditions", "expected", "forbidden", "turns", "severity"}
    missing = required - set(case)
    if missing:
        return [f"缺少字段 {sorted(missing)}"]

    if case["category"] not in CATEGORIES:
        errors.append(f"category 非法: {case['category']}")
    if case["persona"] not in PERSONAS:
        errors.append(f"persona 非法: {case['persona']}")
    if case["severity"] not in {"low", "medium", "high"}:
        errors.append(f"severity 非法: {case['severity']}")
    if not isinstance(case["turns"], list) or not all(isinstance(t, str) for t in case["turns"]):
        errors.append("turns 必须是字符串数组")
    if not case["input"].strip():
        errors.append("input 为空")
    if case["input"].strip() in seen_inputs:
        errors.append("input 与其他题重复")
    seen_inputs.add(case["input"].strip())

    user = case.get("preconditions", {}).get("user")
    if user not in users:
        errors.append(f"preconditions.user 不存在: {user}")
        return errors
    order_ids = set(users[user])
    pre_orders = case["preconditions"].get("orders") or []
    for order_no in pre_orders:
        if order_no not in order_ids:
            errors.append(f"precondition 订单不属于 {user}: {order_no}")

    expected = case["expected"]
    if expected.get("type") not in EXPECTED_TYPES:
        errors.append(f"expected.type 非法: {expected.get('type')}")
    for tool in expected.get("tools") or []:
        if tool not in TOOLS:
            errors.append(f"工具非法: {tool}")
    expected_order = expected.get("order_no")
    if expected_order and expected_order not in order_ids:
        errors.append(f"expected.order_no 不属于 {user}: {expected_order}")
    if expected_order and pre_orders and expected_order not in pre_orders:
        errors.append("expected.order_no 不在 preconditions.orders 中")
    for item in case["forbidden"]:
        if item not in FORBIDDEN:
            errors.append(f"forbidden 非法: {item}")

    order_nos = expected.get("order_nos") or []
    for order_no in order_nos:
        if order_no not in order_ids:
            errors.append(f"expected.order_nos 不属于 {user}: {order_no}")
    if expected.get("type") == "confirm" and not expected_order and not order_nos:
        errors.append("confirm 题必须给 expected.order_no 或 order_nos")
    if expected.get("type") == "refuse":
        creates = [tool for tool in (expected.get("tools") or []) if tool.startswith("create_")]
        if creates:
            errors.append("refuse 不应要求写工具")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--single", action="store_true", help="只验收 single-turn.jsonl")
    parser.add_argument("--confirm", action="store_true", help="只验收 confirmation-scripts.jsonl")
    args = parser.parse_args()
    users = load_orders()
    seen_inputs: set[str] = set()
    all_errors: list[str] = []
    total = 0
    multi = 0
    by_category: Counter[str] = Counter()

    if args.confirm:
        writers = ("confirmation",)
    elif args.single:
        writers = ("single-turn",)
    else:
        writers = ("writer-a", "writer-b", "writer-c")
    for writer in writers:
        if args.confirm:
            path = PILOT / "confirmation-scripts.jsonl"
        elif args.single:
            path = PILOT / "single-turn.jsonl"
        else:
            path = PILOT / f"{writer}.jsonl"
        if not path.exists():
            all_errors.append(f"缺少文件: {path}")
            continue
        cases = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                all_errors.append(f"{path.name}:{line_no} JSON 解析失败: {exc}")
                continue
            cases.append(case)
            errors = check_case(case, writer, users, seen_inputs)
            all_errors.extend(f"{path.name}:{line_no} {error}" for error in errors)
        total += len(cases)
        multi += sum(1 for case in cases if case.get("turns"))
        by_category.update(case.get("category") for case in cases)
        if args.confirm:
            for case in cases:
                if case.get("steps"):
                    steps = case["steps"]
                    if len(steps) < 2:
                        all_errors.append(f"{case.get('id')} 至少 2 步")
                        continue
                    if steps[0]["expect"].get("type") not in {"clarify", "confirm"}:
                        all_errors.append(f"{case.get('id')} 首步必须是 clarify/confirm")
                    if steps[-1]["expect"].get("type") not in {"handled", "answer"}:
                        all_errors.append(f"{case.get('id')} 末步必须是 handled/answer")
                    for step in steps:
                        if not step.get("user") or not step.get("expect"):
                            all_errors.append(f"{case.get('id')} step 缺 user/expect")
                    continue
                steps = case.get("expected_turns") or []
                if len(case.get("turns") or []) != 1 or len(steps) != 2:
                    all_errors.append(f"{case.get('id')} 确认脚本必须是 2 步")
                    continue
                if steps[0].get("type") != "confirm":
                    all_errors.append(f"{case.get('id')} 第一步必须是 confirm")
                if steps[1].get("type") not in {"handled", "answer"}:
                    all_errors.append(f"{case.get('id')} 第二步必须是 handled/answer")
                if steps[0].get("order_no") != case["expected"].get("order_no"):
                    all_errors.append(f"{case.get('id')} 两步订单不一致")
            continue
        if args.single:
            for case in cases:
                if case.get("turns"):
                    all_errors.append(f"{writer} 不应包含多轮题: {case.get('id')}")
            continue
        quota = WRITER_QUOTAS[writer]
        actual = Counter(case.get("category") for case in cases)
        for category, expected_count in quota.items():
            if actual[category] != expected_count:
                all_errors.append(
                    f"{writer} 配额不符: {category} 期望 {expected_count} 实际 {actual[category]}"
                )
        if len(cases) != 10:
            all_errors.append(f"{writer} 题数应为 10，实际 {len(cases)}")

    print(json.dumps({"total": total, "multi_turn": multi, "by_category": dict(by_category)}, ensure_ascii=False))
    if all_errors:
        print("\n".join(all_errors), file=sys.stderr)
        raise SystemExit(1)
    print("PILOT OK")


if __name__ == "__main__":
    main()
