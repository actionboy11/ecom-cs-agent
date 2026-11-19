# Held-out 150 v1.1：表单/拦截契约

日期：2026-11-19  
评测日：`EVAL_TODAY=2026-11-15`  
结果文件：`python-agent/eval/heldout-150-v1.1/results-react.json`

## 结果

| 指标 | 数值 |
|---|---:|
| 总通过 | **128 / 150** |
| 通过率 | **85.3%** |
| 单轮 | 110 / 120 |
| 多步脚本 | 18 / 30 |

## 关键修复

### 1. ui_action 不再被 fallback 丢掉

`prepare_user_action` 成功后进入 `_fallback` 时，保留 `ui_action`。  
单轮表单失败：7 → 0。

### 2. 确定性预取层

新增 `app/graph/preflight.py`：

- 订单：显式订单号 → `query_order`；描述商品 → `find_my_orders`
- 售后进度：`query_after_sales`
- 物流：`query_logistics`
- 运输中退款：先 `intercept`
- 催件：`urge_logistics`

模型不再负责“记不记得先查订单/物流”。

### 3. 契约

- 多候选 → `clarify`
- custom / gift → `handoff`
- 历史账单 → `history`
- 脚本提交原因带质量问题

## 剩余 22 条

| 类型 | 数量 | 说明 |
|---|---:|---|
| 脚本失败 | 12 | 7 条表单未触发；3 条运输中确认；1 条多候选误写；1 条 confirm |
| 工具不匹配 | 8 | 订单不存在、赠品、定制、部分物流 |
| `handoff` 缺失 | 2 | 无订单超期、custom |

### 典型

- `a-s003` / `a-s033`：订单号在本用户下查不到，预取失败
- `b-s010` / `c-s013`：赠品，分类先走 handoff
- `b-s028` / `c-s037`：custom，分类先走 handoff
- `a-c004`：多候选仍误触 `create_refund`
- 脚本表单：`a-c009`、`b-c005/6/8/9`、`c-c005/6/7`

## 下一步

1. 多候选写操作在 **工具层** 强制拒绝（不能只靠 ReAct guard）
2. 脚本表单：复用单轮的 `ui_action` 保活链路
3. 运输中确认：拦截成功后显式确认
4. 工具/标签：把 gift/custom 分类和预取顺序统一
