"""公开基准适配器：把外部 600 条售后集转换成评测用例。

用法：
    python -m eval.public_bench --source /path/to/csnewerst.jsonl

源文件每行需含 `question` 与 `answer`（或 `input`/`must_contain`）。
适配规则：`input=question`，`must_contain` 取 answer 中的关键数字/短语（前 2 个），
`expect_intent` 由关键词粗判（仅用于分层统计，不作为准确率结论）。
数据集不随仓库分发，未提供源文件时本脚本直接退出，不伪造结果。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KEYWORDS = [
    ("policy", ("政策", "规则", "几天", "发票", "价保", "运费")),
    ("refund", ("退款", "退货", "换货")),
    ("logistics", ("物流", "到哪", "快递")),
    ("order_query", ("订单",)),
    ("product_info", ("库存", "多少钱", "尺码", "参数")),
]


def guess_intent(text: str) -> str:
    for intent, words in KEYWORDS:
        if any(word in text for word in words):
            return intent
    return "other"


def adapt(row: dict, index: int) -> dict:
    question = str(row.get("question") or row.get("input") or "").strip()
    answer = str(row.get("answer") or "")
    tokens = [t for t in ("7", "15", "48", "72", "1-3", "3-7", "工作日", "天") if t in answer][:2]
    return {
        "id": f"pub-{index:03d}",
        "input": question,
        "expect_intent": guess_intent(question),
        "expect_tool": False,
        "must_contain": tokens or [answer[:8]] if answer else [],
        "provenance": "public",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="公开基准适配器（不内置数据集）")
    parser.add_argument("--source", required=True, help="外部 JSONL 路径")
    parser.add_argument("--out", default="eval/public_cases.jsonl")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"源文件不存在：{source}（公开集需自行下载）", file=sys.stderr)
        raise SystemExit(2)

    rows = [
        adapt(json.loads(line), i)
        for i, line in enumerate(source.read_text(encoding="utf-8-sig").splitlines())
        if line.strip()
    ]
    Path(args.out).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    print(f"adapted {len(rows)} cases -> {args.out}")


if __name__ == "__main__":
    main()
