"""执行 held-out 150：新 ReAct，保存 transcript 供 judge 使用。"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

from eval.run_pilot import after_sales, chat, check_single, login, reset_order

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "python-agent/eval/heldout-150"
JAVA = "http://localhost:8080"
AGENT = "http://localhost:8000"


def load(pattern: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(BASE.glob(pattern)):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return rows


def check_step(expected: dict, data: dict) -> tuple[bool, str]:
    kind = expected.get("type")
    if kind == "clarify":
        tools = {item.get("tool") for item in (data.get("tool_trace") or []) if item.get("tool")}
        write = (data.get("interrupt") or {}).get("type") == "write_approval"
        return not write and bool(data.get("reply", "").strip()), f"tools={sorted(tools)}"
    return check_single({"expected": expected}, data)


async def run_script(
    client: httpx.AsyncClient, token: str, case: dict, thread: str
) -> dict[str, Any]:
    steps = case.get("steps") or []
    final_order = (steps[-1].get("expect") or {}).get("order_no") if steps else None
    order_no = final_order or (case.get("preconditions", {}).get("orders") or [""])[0]
    if not order_no:
        return {"ok": False, "detail": "missing order", "transcript": [], "reply": ""}
    if not await asyncio.to_thread(reset_order, order_no):
        return {"ok": False, "detail": "reset failed", "transcript": [], "reply": ""}

    transcript: list[dict] = []
    data: dict = {}
    ok = True
    details: list[str] = []
    final_expect: dict = {}

    for step in case.get("steps") or []:
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
            transcript.append({"user": step["user"], "response": data, "confirm": approved})
            details.append(f"{expected['type']}:confirm={approved}:status={resp.status_code}")
            if resp.status_code != 200:
                ok = False
                break
            continue

        data = await chat(client, token, thread, step["user"])
        transcript.append({"user": step["user"], "response": data})
        step_ok, detail = check_step(expected, data)
        details.append(f"{expected.get('type')}:{step_ok}:{detail}")
        if not step_ok:
            ok = False
            break

    if ok:
        matched: list[dict] = []
        for _ in range(5):
            created = await after_sales(client, token)
            matched = [row for row in created if row["orderNo"] == order_no]
            if final_expect.get("type") == "answer":
                break
            if final_expect.get("type") == "handled" and any(
                row["type"] == str(final_expect.get("action", "")).upper() for row in matched
            ):
                break
            await asyncio.sleep(0.2)
        if final_expect.get("type") == "handled":
            ok = any(row["type"] == str(final_expect.get("action", "")).upper() for row in matched)
        elif final_expect.get("type") == "answer":
            ok = not matched
        details.append(f"rows={len(matched)}")

    await asyncio.to_thread(reset_order, order_no)
    return {"ok": ok, "detail": " ".join(details), "transcript": transcript, "reply": data.get("reply", "")}


async def main() -> None:
    singles = load("writer-*-single.jsonl")
    scripts = load("writer-*-scripts.jsonl")
    rows: list[dict] = []
    stamp = int(time.time() * 1000)

    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        tokens: dict[str, str] = {}

        async def token_for(user: str) -> str:
            if user not in tokens:
                tokens[user] = await login(client, user)
            return tokens[user]

        for case in singles:
            user = case["preconditions"]["user"]
            token = await token_for(user)
            thread = f"heldout-{case['id']}-{stamp}"
            data = await chat(client, token, thread, case["input"])
            ok, detail = check_single(case, data)
            rows.append({
                "id": case["id"], "kind": "single", "ok": ok, "detail": detail,
                "expected": case["expected"], "reply": data.get("reply", ""),
                "interrupt": data.get("interrupt"), "tool_trace": data.get("tool_trace") or [],
                "candidates": data.get("candidates") or [], "thread": thread,
            })

        for case in scripts:
            user = case["preconditions"]["user"]
            token = await token_for(user)
            thread = f"heldout-{case['id']}-{stamp}"
            result = await run_script(client, token, case, thread)
            rows.append({
                "id": case["id"], "kind": "script", "ok": result["ok"],
                "detail": result["detail"], "expected": case.get("steps") or [],
                "reply": result["reply"], "transcript": result["transcript"], "thread": thread,
            })

    passed = sum(1 for row in rows if row["ok"])
    report = {
        "system": "react",
        "eval_today": "2026-11-15",
        "cases": len(rows),
        "passed": passed,
        "rate": round(passed / len(rows), 3),
        "rows": rows,
    }
    out = BASE / "results-react.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(rows), "passed": passed, "rate": report["rate"]}, ensure_ascii=False))
    for row in rows:
        if not row["ok"]:
            print("FAIL", row["id"], row["detail"], "|", row["reply"][:100].replace("\n", " "))


if __name__ == "__main__":
    asyncio.run(main())
