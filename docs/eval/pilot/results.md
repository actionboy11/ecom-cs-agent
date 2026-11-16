# Pilot 结果（24 条）

## 总览

- 最近一次：19/24
- 单轮：15/20
- 确认脚本：4/4 中 2 条首步未弹确认（动作类型/日期漂移）

## 失败

| id | 问题 |
|---|---|
| pilot-b-02 | 没调 find_my_orders / order-lookup，直接说查不到 |
| pilot-b-07 | 没调 urge_logistics，只描述物流 |
| pilot-c-02 | 退款请求被模型判成退货确认，动作类型不一致 |
| pilot-confirm-01 | 首步返回 return，不是期望的 refund |
| pilot-confirm-02 | 首步未进入确认，回复称已提交/取消 |

## 关键问题

1. SKILL.md 已接入，但模型不保证先 `load_skill` 再执行
2. 相对时间用例随系统日期漂移：评测基准日 11-15，当前已 11-16
3. 技能文档和实际动作类型（refund/return）需要对齐

## 说明

结构检查，不含语义 judge；样本 24 条，不能外推总体。
