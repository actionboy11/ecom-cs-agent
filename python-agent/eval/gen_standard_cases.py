"""生成「标准层」等效用例（600 条，输入互不重复）。

说明：公开的 600 条售后基准（csnewerst）没有随仓库分发，也无法在离线环境下载。
本脚本用确定性模板 + 变体生成**等效用例**，用于验证三层评测管线与口径；
它不是公开集，报告里必须如实标注。真正接入公开集时用 `eval/public_bench.py`。
"""

from __future__ import annotations

import json
from pathlib import Path

CASES = Path(__file__).parent / "standard_cases.jsonl"

ORDERS = ["CS2024001", "CS2024002", "CS2024003", "CS2024004", "CS2024005", "CS2024006"]
PRODUCTS = ["SKU1001", "SKU1002", "SKU1003"]

TEMPLATES = [
    ("order_query", "查一下订单 {order} 的状态", ["订单"], ORDERS, 6),
    ("logistics", "{order} 到哪了", ["物流"], ORDERS, 6),
    ("refund", "{order} 我要退款", ["退款"], ORDERS, 6),
    ("policy", "退货政策是几天", ["7"], [""], 1),
    ("product_info", "{product} 有货吗", ["库存"], PRODUCTS, 3),
]

PREFIXES = ["", "你好，", "客服你好，", "请问一下，", "麻烦问下，", "在吗，"]

# 20 个口语化后缀变体：与前缀、订单/商品组合出互不重复的输入
SUFFIXES = [
    "", "，谢谢", "，麻烦帮我看看", "，急", "，在线等", "，谢谢啦", "，麻烦快一点",
    "，我这边比较急", "，帮我看下", "，谢谢客服", "，请问", "，有空回我",
    "，我等着呢", "，尽快", "，拜托了", "，感谢", "，麻烦处理下", "，需要多久",
    "，可以吗", "，帮帮忙",
]


def generate(total: int = 600) -> list[dict]:
    rows: list[dict] = []
    per_type = total // len(TEMPLATES)
    for index in range(per_type):
        for kind, template, must, values, value_count in TEMPLATES:
            # 混合基数：值 × 前缀 × 后缀，保证前 per_type 条输入互不重复
            value = values[index % value_count]
            prefix = PREFIXES[(index // value_count) % len(PREFIXES)]
            suffix = SUFFIXES[(index // (value_count * len(PREFIXES))) % len(SUFFIXES)]
            text = prefix + template.format(
                order=value if value.startswith("CS") else ORDERS[index % len(ORDERS)],
                product=value if value.startswith("SKU") else PRODUCTS[index % len(PRODUCTS)],
            )
            rows.append(
                {
                    "id": f"std-{len(rows) + 1:03d}",
                    "input": text + suffix,
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
    print(f"generated {len(rows)} cases (unique inputs: {len({r['input'] for r in rows})})")


if __name__ == "__main__":
    main()
