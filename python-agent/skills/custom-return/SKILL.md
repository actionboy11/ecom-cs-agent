---
name: custom-return
description: 买家要退 tags 含 custom 的定制订单时使用；定制不适用七天无理由，只有质量问题走 P02，否则解释并转人工。
---

# 定制退货

## 前置条件

- 订单 `tags` 含 `custom`
- 用户提出退货/退款

不含 `custom` 时，改用 `normal-return`。

## 步骤

1. 确定订单：有订单号用 `query_order`；没有就先用 `order-lookup`。
   **完成条件**：拿到订单状态、`tags`、`deliveredAt`。

2. 确认 `tags` 含 `custom`。
   **完成条件**：确认是定制；不是就停，改用 `normal-return`。

3. 判断有没有质量问题。
   **完成条件**：从用户描述里确认「开线/破损/发错/故障」等具体问题，或确认没有。

4. 按分支处理：

| 情况 | 动作 |
|---|---|
| 有质量问题、签收 ≤15 天 | 走 P02，`search_policy("质量问题退换")`，确认后 `create_return` |
| 有质量问题、签收 >15 天 | 说明超期，`handoff_to_human` |
| 无质量问题 | 说明定制不适用 P01，`handoff_to_human` |
| 未签收 | 说明签收后才能申请；可拒收或等签收 |

5. 解释时只引用政策原文，不承诺「可以特批」。
   **完成条件**：用户知道为什么不能按普通退货，以及下一步。

6. 需要转人工时，先解释，再调 `handoff_to_human`。
   **完成条件**：出现人工挂起，且用户看到原因。

## 禁止

- 按七天无理由提交定制退货
- 无质量问题时直接 `create_return`
- 承诺一定能退/一定补偿
- 未确认就写

## 示例

用户：「定制的鞋我不要了，退了吧。」

动作：`query_order` → `tags=custom` → 无质量问题 → 说明 P01 不适用 → `handoff_to_human`。

用户：「定制的鞋开线了，签收 3 天。」

动作：`query_order` → `tags=custom` → 有质量问题、≤15 天 → 查 P02 → `create_return` → 等确认。
