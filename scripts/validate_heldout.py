"""校验 held-out 150：配额、订单真实性、归属、泄漏、重复、脚本结构。"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "python-agent/eval/heldout-150"
FIXTURE = ROOT / "docs/eval/fixture-orders.csv"
BLOCKLIST = BASE / "pilot-used-orders.txt"

SINGLE_QUOTAS = {
    "a": {"order_lookup": 8, "logistics": 5, "refund": 7, "normal_return": 7, "custom_return": 3, "exchange": 4, "urge": 3, "policy": 2, "safety": 1},
    "b": {"order_lookup": 8, "logistics": 5, "refund": 7, "normal_return": 7, "custom_return": 3, "exchange": 3, "urge": 4, "policy": 2, "safety": 1},
    "c": {"order_lookup": 9, "logistics": 5, "refund": 6, "normal_return": 6, "custom_return": 4, "exchange": 3, "urge": 3, "policy": 1, "safety": 3},
}
SCRIPT_QUOTAS = {
    "a": {"refund_confirm": 3, "refund_cancel": 1, "return_confirm": 3, "exchange_confirm": 2, "clarify_then_confirm": 1},
    "b": {"refund_confirm": 3, "refund_cancel": 1, "return_confirm": 3, "exchange_confirm": 2, "clarify_then_confirm": 1},
    "c": {"refund_confirm": 2, "refund_cancel": 2, "return_confirm": 2, "exchange_confirm": 1, "clarify_then_confirm": 3},
}
CATEGORIES = set(SINGLE_QUOTAS["a"])
PERSONAS = {"normal", "urgent", "adversarial"}
DIFFICULTIES = {"easy", "normal", "hard"}
SINGLE_TYPES = {"answer", "clarify", "tool", "confirm", "handoff", "refuse"}
STEP_TYPES = {"clarify", "confirm", "handled", "answer"}
TOOLS = {
    "load_skill", "find_my_orders", "query_order", "query_logistics", "get_product",
    "search_policy", "create_refund", "create_return", "create_exchange", "urge_logistics",
}
FORBIDDEN = {"wrong_order", "write_without_confirm", "leak_other", "fabricate_policy", "unsupported_action"}
ORDER_RE = re.compile(r"CS\d{7}")


def load_fixture() -> dict[str, dict[str, str]]:
    users: dict[str, dict[str, str]] = {}
    with FIXTURE.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            users.setdefault(row["user"], {})[row["order_no"]] = row
    return users


def check_base(case: dict, users: dict[str, dict[str, str]], seen: set[str], errors: list[str]) -> None:
    case_id = case.get("id", "?")
    for field in ("id", "category", "persona", "difficulty", "preconditions", "forbidden", "reference"):
        if field not in case:
            errors.append(f"{case_id}: 缺字段 {field}")
    if case.get("category") not in CATEGORIES:
        errors.append(f"{case_id}: category 非法")
    if case.get("persona") not in PERSONAS:
        errors.append(f"{case_id}: persona 非法")
    if case.get("difficulty") not in DIFFICULTIES:
        errors.append(f"{case_id}: difficulty 非法")
    if case_id in seen:
        errors.append(f"{case_id}: id 重复")
    seen.add(case_id)
    for item in case.get("forbidden") or []:
        if item not in FORBIDDEN:
            errors.append(f"{case_id}: forbidden 非法 {item}")
    user = case.get("preconditions", {}).get("user")
    if user not in users:
        errors.append(f"{case_id}: user 不存在")
        return
    for order_no in case.get("preconditions", {}).get("orders") or []:
        if order_no not in users[user]:
            errors.append(f"{case_id}: 订单不属于 {user}: {order_no}")


def check_single(case: dict, users: dict[str, dict[str, str]], blocklist: set[str], errors: list[str]) -> None:
    cid = case.get("id", "?")
    expected = case.get("expected") or {}
    if expected.get("type") not in SINGLE_TYPES:
        errors.append(f"{cid}: expected.type 非法")
    for tool in expected.get("tools") or []:
        if tool not in TOOLS:
            errors.append(f"{cid}: tool 非法 {tool}")
    for tool in expected.get("order_nos") or []:
        if tool not in users.get(case["preconditions"]["user"], {}):
            errors.append(f"{cid}: order_nos 不属于用户")
    order_no = expected.get("order_no")
    if order_no and order_no not in users.get(case["preconditions"]["user"], {}):
        errors.append(f"{cid}: expected.order_no 不属于用户")
    if expected.get("type") == "confirm":
        if not order_no:
            errors.append(f"{cid}: confirm 缺 order_no")
        if "write_without_confirm" not in (case.get("forbidden") or []):
            errors.append(f"{cid}: confirm 缺 write_without_confirm")
    pre = case.get("preconditions", {}).get("orders") or []
    if len(pre) == 1 and pre[0] in blocklist:
        errors.append(f"{cid}: 使用了 pilot 黑名单订单作为唯一依据 {pre[0]}")
    if case.get("turns"):
        errors.append(f"{cid}: 单轮不应有 turns")


def check_script(case: dict, users: dict[str, dict[str, str]], blocklist: set[str], errors: list[str]) -> str:
    cid = case.get("id", "?")
    steps = case.get("steps") or []
    if len(steps) < 2:
        errors.append(f"{cid}: 至少 2 步")
        return "invalid"
    if steps[-1].get("expect", {}).get("type") not in {"handled", "answer"}:
        errors.append(f"{cid}: 最后一步必须 handled/answer")
    for step in steps:
        if not step.get("user") or not step.get("expect"):
            errors.append(f"{cid}: step 缺 user/expect")
            continue
        kind = step["expect"].get("type")
        if kind not in STEP_TYPES:
            errors.append(f"{cid}: step type 非法 {kind}")
        order_no = step["expect"].get("order_no")
        if order_no and order_no not in users.get(case["preconditions"]["user"], {}):
            errors.append(f"{cid}: step 订单不属于用户")
    pre = case.get("preconditions", {}).get("orders") or []
    if len(pre) == 1 and pre[0] in blocklist:
        errors.append(f"{cid}: 使用了 pilot 黑名单订单作为唯一依据 {pre[0]}")
    final = steps[-1]["expect"].get("type")
    if final == "answer":
        return "refund_cancel"
    if steps[0]["expect"].get("type") == "clarify":
        return "clarify_then_confirm"
    action = steps[-1]["expect"].get("action")
    return f"{action}_confirm"


def main() -> None:
    users = load_fixture()
    blocklist = set(BLOCKLIST.read_text(encoding="utf-8").split())
    seen: set[str] = set()
    seen_inputs: set[str] = set()
    errors: list[str] = []
    totals = Counter()
    for writer in ("a", "b", "c"):
        single_path = BASE / f"writer-{writer}-single.jsonl"
        script_path = BASE / f"writer-{writer}-scripts.jsonl"
        singles = [json.loads(line) for line in single_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        scripts = [json.loads(line) for line in script_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(singles) != 40:
            errors.append(f"writer-{writer}: 单轮应为 40，实际 {len(singles)}")
        if len(scripts) != 10:
            errors.append(f"writer-{writer}: 脚本应为 10，实际 {len(scripts)}")

        actual_single = Counter()
        explicit = 0
        hard = 0
        for case in singles:
            check_base(case, users, seen, errors)
            check_single(case, users, blocklist, errors)
            actual_single[case.get("category")] += 1
            hard += case.get("difficulty") == "hard"
            explicit += bool(ORDER_RE.search(case.get("input", "")))
            text = case.get("input", "").strip()
            if text in seen_inputs:
                errors.append(f"{case['id']}: input 重复")
            seen_inputs.add(text)
        for category, want in SINGLE_QUOTAS[writer].items():
            if actual_single[category] != want:
                errors.append(f"writer-{writer}: {category} 期望 {want} 实际 {actual_single[category]}")
        if hard < 10:
            errors.append(f"writer-{writer}: hard 少于 10（{hard}）")
        if explicit > 20:
            errors.append(f"writer-{writer}: 报订单号的单轮超过 50%（{explicit}/40）")

        actual_script = Counter()
        for case in scripts:
            check_base(case, users, seen, errors)
            actual_script[check_script(case, users, blocklist, errors)] += 1
            text = case.get("input") or " ".join(s.get("user", "") for s in case.get("steps") or [])
            if text in seen_inputs:
                errors.append(f"{case['id']}: input 重复")
            seen_inputs.add(text)
        for scenario, want in SCRIPT_QUOTAS[writer].items():
            if actual_script[scenario] != want:
                errors.append(f"writer-{writer}: {scenario} 期望 {want} 实际 {actual_script[scenario]}")
        totals["single"] += len(singles)
        totals["scripts"] += len(scripts)

    print(json.dumps({**totals, "errors": len(errors)}, ensure_ascii=False))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print("HELDOUT 150 OK")


if __name__ == "__main__":
    main()
