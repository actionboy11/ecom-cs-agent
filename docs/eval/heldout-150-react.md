# Held-out 150：ReAct 第二次跑

## 总览

- 系统：新 ReAct
- 基准日：`2026-11-15`
- 结果：**99/150（66%）**
- 单轮：80/120
- 确认脚本：19/30

## 分类别

| 类别 | 通过/总数 |
|---|---|
| order_lookup | 23/25 |
| policy | 5/5 |
| refund | 34/37 |
| custom_return | 7/10 |
| logistics | 11/15 |
| normal_return | 9/28 |
| exchange | 4/15 |
| urge | 4/10 |
| safety | 2/5 |

## 本次修复

- 上一轮有候选时，下一句即使没有商品词也进 ReAct
- 候选状态持久化（last_candidates）
- 显式日期解析（10月28号）
- 用户选单后锁定订单
- 确认脚本按最终选中订单重置数据

## 仍然失败

- 15/40 confirm 未弹确认
- 2/13 handoff 未挂起
- 4/10 urge 未调工具
- 5 条 `confirm + urge` 是题面期望写错
- 多条多候选 confirm 本身要求 Agent 猜单

## 说明

结构检查，不是语义 judge；基线/judge/人工校准未做；题集已冻结。
