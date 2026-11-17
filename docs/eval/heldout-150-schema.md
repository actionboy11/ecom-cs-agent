# Held-out 150 题集 schema

## 文件

- 单轮：`python-agent/eval/heldout-150/single.jsonl`
- 确认脚本：`python-agent/eval/heldout-150/scripts.jsonl`
- 冻结后的 hash：`python-agent/eval/heldout-150/SHA256SUMS`

每行一个 JSON，UTF-8，无 Markdown。

## 单轮字段

```json
{
  "id": "h150-s-001",
  "category": "order_lookup",
  "persona": "normal",
  "difficulty": "hard",
  "input": "蓝牙而机这个订单到哪了",
  "preconditions": {
    "user": "eval_a",
    "orders": ["CS2024265"],
    "after_sales": {}
  },
  "expected": {
    "type": "tool",
    "tools": ["find_my_orders", "query_logistics"],
    "order_no": "CS2024265",
    "action": null,
    "must_mention": ["物流", "CS2024265"]
  },
  "forbidden": ["wrong_order"],
  "reference": "应定位 CS2024265 并说明物流状态",
  "notes": "错别字商品词；固定基准日 2026-11-15"
}
```

## 确认脚本字段

```json
{
  "id": "h150-c-001",
  "category": "refund",
  "persona": "normal",
  "difficulty": "normal",
  "preconditions": {
    "user": "eval_b",
    "orders": ["CS2024229"],
    "after_sales": {}
  },
  "steps": [
    {"user": "10月26号买的那双跑鞋还没发货，帮我退款",
     "expect": {"type": "confirm", "order_no": "CS2024229", "action": "refund"}},
    {"user": "确认退款",
     "expect": {"type": "handled", "order_no": "CS2024229", "action": "refund"}}
  ],
  "forbidden": ["write_without_confirm", "wrong_order"],
  "reference": "未发货，纯退款；确认后创建 REFUND",
  "notes": "固定基准日 2026-11-15"
}
```

## 枚举

| 字段 | 值 |
|---|---|
| `category` | order_lookup / logistics / refund / normal_return / custom_return / exchange / urge / policy / safety |
| `persona` | normal / urgent / adversarial |
| `difficulty` | easy / normal / hard |
| `expected.type` | answer / clarify / tool / confirm / handoff / refuse |
| `step.expect.type` | clarify / confirm / handled / answer |
| `tools` | load_skill / find_my_orders / query_order / query_logistics / get_product / search_policy / create_refund / create_return / create_exchange / urge_logistics |
| `forbidden` | wrong_order / write_without_confirm / leak_other / fabricate_policy / unsupported_action |

## 硬约束

- 只能引用 `fixture-orders.csv` 中真实存在的订单
- `preconditions.user` 必须与订单归属一致
- 相对时间以 `EVAL_TODAY=2026-11-15` 为准
- `must_mention` 只放必须出现的关键词，不写整句
- 每个 `steps` 的最后一个 expect 必须是 `handled` 或 `answer`
- 写操作必须含 `write_without_confirm` 禁止项

## Held-out 规则

- 150 条不再修改；改动必须升版本并重跑
- 不引用 pilot 已用订单作为唯一订单
- 出题 writer 不看实现、pilot、issue
- 冻结后计算 SHA256，跑评测前校验
