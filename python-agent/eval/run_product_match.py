"""商品实体链接测试集执行器。"""

from __future__ import annotations

import json
from pathlib import Path

from app.nlp.product_match import match_products

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "python-agent/eval/product_match_cases.jsonl"


def main() -> None:
    rows = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    failed: list[str] = []
    for case in rows:
        actual = match_products(case["input"])
        expected = case["expected"]
        actual_matches = [(item["canonical"], tuple(item["span"])) for item in actual["matches"]]
        expected_matches = [(item["canonical"], tuple(item["span"])) for item in expected["matches"]]
        actual_unknown = [(item["surface"], tuple(item["span"])) for item in actual["unknown"]]
        expected_unknown = [(item["surface"], tuple(item["span"])) for item in expected["unknown"]]
        if actual_matches != expected_matches or actual_unknown != expected_unknown:
            failed.append(
                f"{case['id']} input={case['input']!r} "
                f"actual={actual_matches}/{actual_unknown} expected={expected_matches}/{expected_unknown}"
            )
    print(json.dumps({"cases": len(rows), "passed": len(rows) - len(failed), "failed": len(failed)}, ensure_ascii=False))
    for item in failed:
        print("FAIL", item)


if __name__ == "__main__":
    main()
