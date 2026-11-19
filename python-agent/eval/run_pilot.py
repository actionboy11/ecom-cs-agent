"""Pilot 执行器：单轮 + 多步确认脚本。

确认脚本支持两种写法：
- 旧版：input + turns[0] + expected_turns
- 新版：steps[{user, expect}]，可表达「澄清 → 选单 → 确认/取消」
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "docs/eval/pilot"
JAVA = "http://localhost:8080"
AGENT = "http://localhost:8000"


def reset_order(order_no: str) -> bool:
    result = subprocess.run(
        [
            "mysql", "-h", "127.0.0.1", "-P", "3308", "-ucsagent", "-pcsagent",
            "cs_agent", "-e", f"DELETE FROM after_sales_requests WHERE order_no='{order_no}';",
        ],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    return result.returncode == 0


async def login(client: httpx.AsyncClient, user: str) -> str:
    resp = await client.post(f"{JAVA}/api/auth/login", json={"username": user, "password": "demo123"})
    resp.raise_for_status()
    return resp.json()["token"]


async def chat(client: httpx.AsyncClient, token: str, thread: str, message: str) -> dict:
    resp = await client.post(
        f"{AGENT}/api/v1/chat",
        json={"thread_id": thread, "message": message},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


async def after_sales(client: httpx.AsyncClient, token: str) -> list[dict]:
    resp = await client.get(f"{JAVA}/api/after-sales", headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    return resp.json()


def check_single(case: dict, data: dict) -> tuple[bool, str]:
    expected = case["expected"]
    kind = expected.get("type")
    tools = {item.get("tool") for item in (data.get("tool_trace") or []) if item.get("tool")}
    interrupt = data.get("interrupt") or {}
    write = interrupt.get("type") == "write_approval"
    expected_tools = set(expected.get("tools") or [])
    orders = set(expected.get("order_nos") or [])
    if expected.get("order_no"):
        orders.add(expected["order_no"])

    if kind == "history":
        return bool(data.get("history_request")) and not write, f"history={bool(data.get('history_request'))}"
    if kind == "user_action":
        action = (data.get("ui_action") or {})
        ok = bool(action) and action.get("action") == expected.get("action")
        orders = set(expected.get("order_nos") or [])
        if expected.get("order_no"):
            orders.add(expected["order_no"])
        if orders:
            ok = ok and action.get("order_no") in orders
        fields = expected.get("fields") or []
        if fields:
            ok = ok and all(field in (action.get("fields") or []) for field in fields)
        return ok, f"ui_action={action.get('action')}/{action.get('order_no')}"
    if kind == "confirm":
        ok = write and (not expected.get("action") or interrupt.get("action") == expected.get("action"))
        if orders:
            ok = ok and interrupt.get("order_no") in orders
        return ok, f"interrupt={interrupt.get('action')}/{interrupt.get('order_no')}"
    if kind == "handoff":
        return interrupt.get("type") == "human_handoff", f"interrupt={interrupt.get('type')}"
    if kind == "refuse":
        creates = {name for name in tools if name.startswith("create_")}
        return not write and not creates, f"tools={sorted(tools)}"
    if kind == "answer":
        return not write and bool(data.get("reply", "").strip()), f"tools={sorted(tools)}"
    if kind in {"tool", "clarify"}:
        if write:
            return False, "unexpected write"
        if expected_tools and not (expected_tools & tools):
            return False, f"expected {sorted(expected_tools)} got {sorted(tools)}"
        return True, f"tools={sorted(tools)}"
    return False, f"unknown expected type {kind}"


def check_step(expected: dict, data: dict) -> tuple[bool, str]:
    kind = expected.get("type")
    if kind == "clarify":
        tools = {item.get("tool") for item in (data.get("tool_trace") or []) if item.get("tool")}
        write = (data.get("interrupt") or {}).get("type") == "write_approval"
        return not write and bool(data.get("reply", "").strip()), f"tools={sorted(tools)}"
    return check_single({"expected": expected}, data)


def default_steps(case: dict) -> list[dict[str, Any]]:
    return [
        {"user": case["input"], "expect": case["expected"]},
        {"user": (case.get("turns") or [""])[0], "expect": case["expected_turns"][1]},
    ]


async def run_confirmation(
    client: httpx.AsyncClient, token: str, case: dict, stamp: int
) -> dict[str, Any]:
    steps = case.get("steps") or default_steps(case)
    order_no = (case.get("preconditions", {}).get("orders") or [case.get("expected", {}).get("order_no")])[0]
    if not order_no:
        return {"ok": False, "detail": "missing order", "reply": ""}
    if not await asyncio.to_thread(reset_order, order_no):
        return {"ok": False, "detail": "reset failed", "reply": ""}

    thread = f"pilot-{case['id']}-{stamp}"
    data: dict = {}
    details: list[str] = []
    ok = True
    final_expect: dict = {}

    for step in steps:
        expected = step["expect"]
        final_expect = expected
        if expected.get("type") in {"handled", "answer"} and (data.get("interrupt") or {}).get("type") == "write_approval":
            approved = expected.get("type") == "handled"
            resp = await client.post(
                f"{AGENT}/api/v1/threads/{thread}/confirm",
                json={"approved": approved},
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json() if resp.status_code == 200 else {}
            details.append(f"{expected['type']}:confirm={approved}")
            continue

        data = await chat(client, token, thread, step["user"])
        step_ok, detail = check_step(expected, data)
        details.append(f"{expected.get('type')}:{step_ok}:{detail}")
        if not step_ok:
            ok = False
            break

    if ok:
        created = await after_sales(client, token)
        matched = [row for row in created if row["orderNo"] == order_no]
        if final_expect.get("type") == "handled":
            ok = any(row["type"] == str(final_expect.get("action", "")).upper() for row in matched)
        elif final_expect.get("type") == "answer":
            ok = not matched
        details.append(f"rows={len(matched)}")

    await asyncio.to_thread(reset_order, order_no)
    return {
        "ok": ok,
        "detail": " ".join(details),
        "reply": data.get("reply", ""),
    }


async def main() -> None:
    singles = [
        json.loads(line)
        for line in (PILOT / "single-turn.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    confirms = [
        json.loads(line)
        for line in (PILOT / "confirmation-scripts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    rows = []
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        tokens: dict[str, str] = {}

        async def token_for(user: str) -> str:
            if user not in tokens:
                tokens[user] = await login(client, user)
            return tokens[user]

        stamp = int(asyncio.get_running_loop().time() * 1000)
        for case in singles:
            user = case["preconditions"]["user"]
            token = await token_for(user)
            data = await chat(client, token, f"pilot-{case['id']}-{stamp}", case["input"])
            ok, detail = check_single(case, data)
            rows.append({"id": case["id"], "kind": "single", "ok": ok, "detail": detail,
                         "expected": case["expected"].get("type"), "reply": data.get("reply", "")})

        for case in confirms:
            user = case["preconditions"]["user"]
            token = await token_for(user)
            result = await run_confirmation(client, token, case, stamp)
            rows.append({
                "id": case["id"], "kind": "confirm", "ok": result["ok"],
                "detail": result["detail"], "expected": "confirm", "reply": result["reply"],
            })

    passed = sum(1 for row in rows if row["ok"])
    report = {"cases": len(rows), "passed": passed, "rate": round(passed / len(rows), 3), "rows": rows}
    (PILOT / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(rows), "passed": passed, "rate": report["rate"]}, ensure_ascii=False))
    for row in rows:
        if not row["ok"]:
            print("FAIL", row["id"], row["kind"], row["detail"], "|", row["reply"][:120].replace("\n", " "))


if __name__ == "__main__":
    asyncio.run(main())
