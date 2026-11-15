"""Pilot 执行器：20 条单轮 + 4 条确认脚本。

单轮：核对工具/确认/转人工/拒答/不落单。
确认脚本：第一步必须 interrupt，第二步按确认/取消执行，并核对售后单。
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "docs/eval/pilot"
JAVA = "http://localhost:8080"
AGENT = "http://localhost:8000"


def reset_order(order_no: str) -> None:
    subprocess.run(
        [
            "docker", "compose", "exec", "-T", "mysql", "mysql", "-ucsagent", "-pcsagent",
            "cs_agent", "-e", f"DELETE FROM after_sales_requests WHERE order_no='{order_no}';",
        ],
        cwd=str(ROOT), capture_output=True, check=False,
    )


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
        stamp = int(asyncio.get_running_loop().time() * 1000)
        for case in singles:
            user = case["preconditions"]["user"]
            token = tokens.setdefault(user, await login(client, user))
            data = await chat(client, token, f"pilot-{case['id']}-{stamp}", case["input"])
            ok, detail = check_single(case, data)
            rows.append({"id": case["id"], "kind": "single", "ok": ok, "detail": detail,
                         "expected": case["expected"].get("type"), "reply": data.get("reply", "")})

        for case in confirms:
            user = case["preconditions"]["user"]
            order_no = case["expected"]["order_no"]
            token = tokens.setdefault(user, await login(client, user))
            await asyncio.to_thread(reset_order, order_no)
            first = await chat(client, token, f"pilot-{case['id']}-{stamp}", case["input"])
            interrupt = first.get("interrupt") or {}
            first_ok = (
                interrupt.get("type") == "write_approval"
                and interrupt.get("action") == case["expected"]["action"]
                and interrupt.get("order_no") == order_no
            )
            step2 = case["expected_turns"][1]
            approved = step2.get("type") == "handled"
            second = await client.post(
                f"{AGENT}/api/v1/threads/pilot-{case['id']}/confirm",
                json={"approved": approved},
                headers={"Authorization": f"Bearer {token}"},
            )
            second_data = second.json() if second.status_code == 200 else {}
            created = await after_sales(client, token)
            matched = [row for row in created if row["orderNo"] == order_no]
            if approved:
                ok = first_ok and bool(matched) and matched[0]["type"] == case["expected"]["action"].upper()
            else:
                ok = first_ok and not matched
            rows.append({
                "id": case["id"], "kind": "confirm", "ok": ok,
                "detail": f"first={first_ok} approved={approved} rows={len(matched)}",
                "expected": case["expected"]["action"], "reply": second_data.get("reply", ""),
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
