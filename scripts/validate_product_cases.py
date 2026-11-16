"""校验商品实体链接测试集的结构与 span，不执行匹配。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "python-agent/eval/product_match_cases.jsonl"
TYPES = {"exact", "alias", "typo", "compound", "multi", "none", "ambiguous"}


def check_span(text: str, item: dict, label: str, errors: list[str], case_id: str) -> tuple[int, int]:
    span = item.get("span")
    if not (isinstance(span, list) and len(span) == 2 and all(isinstance(v, int) for v in span)):
        errors.append(f"{case_id}: {label} span 非法")
        return (0, 0)
    start, end = span
    if not (0 <= start < end <= len(text)):
        errors.append(f"{case_id}: {label} span 越界 {span}")
        return (start, end)
    surface = item.get("surface")
    if text[start:end] != surface:
        errors.append(f"{case_id}: {label} surface={surface!r} 与原文 {text[start:end]!r} 不符")
    return (start, end)


def main() -> None:
    errors: list[str] = []
    seen: set[str] = set()
    total = 0
    for line_no, line in enumerate(CASES.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        total += 1
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: JSON 解析失败: {exc}")
            continue
        case_id = case.get("id", f"line{line_no}")
        if case_id in seen:
            errors.append(f"{case_id}: id 重复")
        seen.add(case_id)
        if case.get("type") not in TYPES:
            errors.append(f"{case_id}: type 非法 {case.get('type')}")
        text = case.get("input", "")
        expected = case.get("expected") or {}
        ranges = []
        for item in expected.get("matches") or []:
            if not item.get("canonical"):
                errors.append(f"{case_id}: match 缺 canonical")
            ranges.append(check_span(text, item, "match", errors, case_id))
        for item in expected.get("unknown") or []:
            ranges.append(check_span(text, item, "unknown", errors, case_id))
        for i in range(len(ranges)):
            for j in range(i + 1, len(ranges)):
                a, b = ranges[i], ranges[j]
                if max(a[0], b[0]) < min(a[1], b[1]):
                    errors.append(f"{case_id}: span 重叠 {a} {b}")
        if case.get("type") == "none" and (expected.get("matches") or expected.get("unknown")):
            errors.append(f"{case_id}: none 题不应有 match/unknown")
        if case.get("type") == "compound" and expected.get("matches"):
            errors.append(f"{case_id}: compound 题不应有 match")

    print(json.dumps({"cases": total, "errors": len(errors)}, ensure_ascii=False))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print("PRODUCT MATCH CASES OK")


if __name__ == "__main__":
    main()
