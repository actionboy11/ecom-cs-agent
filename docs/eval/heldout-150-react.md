# Held-out 150：ReAct 首跑

## 总览

- 系统：新 ReAct
- 基准日：`2026-11-15`
- 结果：**90/150（60%）**
- 单轮：77/120
- 确认脚本：13/30

## 分类别

| 类别 | 通过/总数 |
|---|---|
| order_lookup | 23/25 |
| policy | 5/5 |
| custom_return | 7/10 |
| logistics | 10/15 |
| refund | 26/37 |
| normal_return | 10/28 |
| exchange | 4/15 |
| urge | 3/10 |
| safety | 2/5 |

## 按期望类型

| 期望 | 通过/总数 |
|---|---|
| clarify | 29/29 |
| answer | 11/12 |
| refuse | 3/3 |
| tool | 24/34 |
| confirm | 13/40 |
| handoff | 2/13 |
| script | 8/19（其余脚本未写 expected） |

## 主要失败模式

1. 期望 `confirm`，Agent 先让用户选单：13/40 通过
2. 期望 `handoff`，Agent 直接回答：2/13 通过
3. 催件没有调 `urge_logistics`：3/10
4. 正常退货/换货在选单或时效分支停住：10/28、4/15
5. 确认脚本 17 条失败，多数是订单定位/动作类型不稳定

## 说明

- 这是结构检查，不是语义 judge
- 尚未跑规则基线、旧 workflow
- 尚未人工校准
- 首跑结果不能直接称为“系统准确率 60%”
- 题集已冻结，后续不能按这份结果改题
