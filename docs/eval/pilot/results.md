# Pilot 结果（24 条）

## 总览

- 最近一次：22/24
- 单轮：18/20
- 确认脚本：4/4 中 3 条通过；confirm-01 动作类型不一致

## 已修

| id | 修复 |
|---|---|
| pilot-b-02 | Java 商品 canonical/aliases → Python 目录 → matcher → hard rule → ReAct；实测 `intent=logistics`，调用 find_my_orders/query_logistics |

## 未修

| id | 问题 |
|---|---|
| pilot-b-07 | `urge_logistics` 未注册到 ReAct，模型只能描述物流 |
| pilot-confirm-01 | 用户说退款，模型选择 RETURN，首步 action 与期望不一致 |

## 说明

- 结构检查，不含语义 judge
- 24 条只验证链路，不能外推总体
- 评测基准日仍需固定，相对时间用例会漂移
