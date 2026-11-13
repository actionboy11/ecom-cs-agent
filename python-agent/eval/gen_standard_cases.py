"""生成「标准层」等效用例（600 条）。

说明：公开的 600 条售后基准（csnewerst）没有随仓库分发，也无法在离线环境下载。
本脚本用确定性模板生成**等效用例**，用于验证「三层评测」的管线与任务完成率口径；
它不是公开集，报告里必须如实标注。真正接入公开集时，用 `eval/public_bench.py` 适配。
"""

from __future__ import annotations

import json
from pathlib import Path

CASES = Path(__file__).parent / "standard_cases.jsonl"

# 5 类 × 120 条 = 600
TEMPLATES = [
    ("order_query", "查一下订单 {order} 的状态", ["订单"]),
    ("logistics", "{order} 到哪了", ["物流"]),
    ("refund", "{order} 我要退款", ["退款"]),
    ("policy", "退货政策是几天", ["7"]),
    ("product_info", "{product} 有货吗", ["库存"]),
]

ORDERS = ["CS2024001", "CS2024002", "CS2024003", "CS2024004", "CS2024005", "CS2024006"]
PRODUCTS = ["SKU1001", "SKU1002", "SKU1003"]


def generate(total: int = 600) -> list[dict]:
    rows: list[dict] = []
    per_type = total // len(TEMPLATES)
    for index in range(per_type):
        for kind, template, must in TEMPLATES:
            rows.append(
                {
                    "id": f"std-{len(rows) + 1:03d}",
                    "input": template.format(
                        order=ORDERS[index % len(ORDERS)], product=PRODUCTS[index % len(PRODUCTS)]
                    ),
                    "expect_intent": kind,
                    "expect_tool": kind != "policy",
                    "must_contain": must,
                    "provenance": "local-equivalent",
                }
            )
    return rows[:total]


def main() -> None:
    rows = generate()
    CASES.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    print(f"generated {len(rows)} cases -> {CASES}")


if __name__ == "__main__":
    main()
