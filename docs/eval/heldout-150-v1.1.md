# Held-out 150 v1.1：表单/拦截契约

日期：2026-11-19  
评测日：`EVAL_TODAY=2026-11-15`  
结果文件：`python-agent/eval/heldout-150-v1.1/results-react.json`

## 结果

| 指标 | 数值 |
|---|---:|
| 总通过 | **120 / 150** |
| 通过率 | **80.0%** |
| 单轮 | 102 / 120 |
| 多步脚本 | 18 / 30 |

v1 旧契约：96/150。  
v1.1 不覆盖 v1，两者不能直接混用。

## v1 与 v1.1 的差别

- 已签收退货/换货 → `user_action` + 表单
- 表单提交通过 `POST /api/after-sales` 验证
- 催件 → `urge_logistics`
- 运输中 → `intercept`
- 多候选 → `clarify`，不再强制表单
- custom / gift → `handoff`

## 剩余 30 条

| 类型 | 数量 | 说明 |
|---|---:|---|
| 脚本失败 | 12 | 表单未触发；1 条提交 409；运输中确认 |
| 工具不匹配 | 10 | 售后进度、物流、催件 |
| `user_action` 未触发 | 6 | 8–15 天质量表单、状态不稳定 |
| `handoff` 缺失 | 2 | 无订单超期、地址多候选 |

### 典型

- `a-s003`：售后进度问题没有先 `query_order`
- `a-s004`：历史账单返回 `order_history`，仍期望 `find_my_orders`
- `a-s021`：充电宝订单选择与期望不一致
- `a-c007`：表单提交 409，脚本原因没带“质量问题”
- `b-s027`：无具体订单的超期退货
- `c-s035`：地址多候选，v1.1 仍期望 handoff，应改为 clarify

## 本轮代码

- runner 支持 `user_action`、`submit`、`intercept`
- v1.1 独立目录 + SHA256
- 资格引擎增加 `custom` / `gift`
- 多候选写操作 guard
- `prepare_user_action` 支持 `quality`
- 表单兜底：唯一订单 + 资格允许 → `user_action`
- 响应增加 `active_order_no`

## 下一步

1. 工具链修正 10 条
2. 6 条表单未触发逐段定位
3. 运输中脚本 `c-c001/c-c002/c-c004`
4. v1.2 或 v2 独立盲测
