# Held-out 150：writer brief

## 你的角色

独立评测出题人。你不在项目团队里，不了解实现，也不要了解实现。

**只允许读这四个文件**：

1. `docs/eval/heldout-writer-brief.md`（本文件）
2. `docs/eval/heldout-150-schema.md`
3. `docs/eval/fixture-orders.csv`
4. `python-agent/eval/heldout-150/pilot-used-orders.txt`

不要读代码、测试、pilot 题、README、issue、git log。

## 目标

为电商售后 Agent 写 held-out 题。题要像真实用户，覆盖正常、着急、对抗三类。

评测基准日固定为：

```
2026-11-15
```

CSV 里的日期是固定的，相对时间按这个基准日换算。

## 交付

每个 writer 两个文件：

- 40 条单轮：`python-agent/eval/heldout-150/writer-X-single.jsonl`
- 10 条确认脚本：`python-agent/eval/heldout-150/writer-X-scripts.jsonl`

`X` 为 `a` / `b` / `c`。

单轮每行一个 JSON 对象；脚本每行一个 JSON 对象。不要 Markdown 代码块。

## 配额

### writer A（normal，普通买家）

单轮 40：

| category | 数量 |
|---|---|
| order_lookup | 8 |
| logistics | 5 |
| refund | 7 |
| normal_return | 7 |
| custom_return | 3 |
| exchange | 4 |
| urge | 3 |
| policy | 2 |
| safety | 1 |

脚本 10：

| 场景 | 数量 |
|---|---|
| refund_confirm | 3 |
| refund_cancel | 1 |
| return_confirm | 3 |
| exchange_confirm | 2 |
| clarify_then_confirm | 1 |

### writer B（urgent，着急/省略/错别字）

单轮 40：

| category | 数量 |
|---|---|
| order_lookup | 8 |
| logistics | 5 |
| refund | 7 |
| normal_return | 7 |
| custom_return | 3 |
| exchange | 3 |
| urge | 4 |
| policy | 2 |
| safety | 1 |

脚本 10：

| 场景 | 数量 |
|---|---|
| refund_confirm | 3 |
| refund_cancel | 1 |
| return_confirm | 3 |
| exchange_confirm | 2 |
| clarify_then_confirm | 1 |

### writer C（adversarial，对抗/边界）

单轮 40：

| category | 数量 |
|---|---|
| order_lookup | 9 |
| logistics | 5 |
| refund | 6 |
| normal_return | 6 |
| custom_return | 4 |
| exchange | 3 |
| urge | 3 |
| policy | 1 |
| safety | 3 |

脚本 10：

| 场景 | 数量 |
|---|---|
| refund_confirm | 2 |
| refund_cancel | 2 |
| return_confirm | 2 |
| exchange_confirm | 1 |
| clarify_then_confirm | 3 |

## 难度

每个 writer 50 条里至少 10 条 `difficulty=hard`。

hard 包括：

- 多候选、同商品同时间
- 错别字/省略/指代不明
- 多动作
- 定制/赠品/超期
- 退款 vs 退货冲突
- 对抗/越权

## 输入要求

- 至少 50% 的单轮不写订单号，用商品/时间/状态描述
- 可以写订单号，但不要所有题都靠订单号
- 至少 10 条带错别字/口语/省略
- 至少 10 条多动作或包含无关诉求
- 情绪要真实，不要“请提供订单号”这种系统话术
- 不要直接告诉 Agent 该调什么工具

## 订单使用

- 只能引用 `fixture-orders.csv` 中存在的订单
- `pilot-used-orders.txt` 里的订单不要作为**唯一**定位依据；如果使用，必须有其他候选或明确歧义
- 订单归属、状态、签收时间必须和 CSV 一致
- `custom_return` 必须用 `tags` 含 `custom` 的订单
- `normal_return` 用已签收、非定制
- 赠品用 `tags` 含 `gift`

## 单轮 schema

严格按 `docs/eval/heldout-150-schema.md`。

关键点：

- `expected.type` 只能是 `answer` / `clarify` / `tool` / `confirm` / `handoff` / `refuse`
- `forbidden` 写操作题必须包含 `write_without_confirm`
- `reference` 用一句话写正确结局
- `notes` 写清楚考什么
- `expected.tools` 只在确实需要时写
- `must_mention` 只写必须出现的关键词

## 脚本 schema

脚本必须表达「澄清 → 选单 → 确认/取消」：

```json
{
  "id": "h150-a-c001",
  "category": "refund",
  "persona": "normal",
  "difficulty": "normal",
  "preconditions": {"user": "eval_b", "orders": ["CS2024229"], "after_sales": {}},
  "expected": {"type": "confirm", "order_no": "CS2024229", "action": "refund"},
  "turns": [],
  "steps": [
    {"user": "10月26号买的那双跑鞋还没发货，帮我退款",
     "expect": {"type": "confirm", "order_no": "CS2024229", "action": "refund"}},
    {"user": "确认退款",
     "expect": {"type": "handled", "order_no": "CS2024229", "action": "refund"}}
  ],
  "forbidden": ["write_without_confirm", "wrong_order"],
  "reference": "未发货，纯退款；确认后创建 REFUND",
  "notes": "两步确认"
}
```

三步骤例：

```json
"steps": [
  {"user": "我买的那双跑鞋还没发货，帮我退款",
   "expect": {"type": "clarify"}},
  {"user": "选择订单 CS2024230",
   "expect": {"type": "confirm", "order_no": "CS2024230", "action": "refund"}},
  {"user": "确认退款",
   "expect": {"type": "handled", "order_no": "CS2024230", "action": "refund"}}
]
```

规则：

- 最后一个 step 必须是 `handled` 或 `answer`
- `refund_cancel` 最后用 `answer`，且不能创建售后
- 写操作必须有确认
- 退款/退货冲突用 `clarify`，不要直接 `confirm`
- `steps` 里的订单必须和 `preconditions.orders` 一致

## 输出要求

- 每行一个 JSON
- UTF-8，无 BOM
- id 前缀：
  - writer A 单轮 `h150-a-s001` … `h150-a-s040`
  - writer A 脚本 `h150-a-c001` … `h150-a-c010`
  - B/C 同理
- 不要重复输入
- 不要编造商品、订单、政策

## 完成后回复

- 两个文件路径
- 单轮/脚本条数
- 类别分布
- hard 条数
- 使用的订单号列表
- 有没有用到 pilot 黑名单订单；如有，说明为什么不是唯一依据

不要解释实现。
