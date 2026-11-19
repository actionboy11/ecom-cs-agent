# Held-out 150 v1.1：表单/拦截契约

日期：2026-11-19  
评测日：`EVAL_TODAY=2026-11-15`  
结果文件：`python-agent/eval/heldout-150-v1.1/results-react.json`

## 结果

| 指标 | 数值 |
|---|---:|
| 总通过 | **127 / 150** |
| 通过率 | **84.7%** |
| 单轮 | 108 / 120 |
| 多步脚本 | 19 / 30 |

## 这一轮的关键修复

`prepare_user_action` 成功后，如果 ReAct 进入 `_fallback`（步数/模型异常），原实现会丢掉 `ui_action`。  
现在 fallback 前保留表单：

```python
if ui_action is not None:
    return {... "ui_action": ui_action}
```

效果：

- 单轮 `user_action` 失败：7 → 0
- 表单不再“prepare 成功但前端没表单”
- 116 → 127

## 剩余 23 条

| 类型 | 数量 | 说明 |
|---|---:|---|
| 脚本失败 | 11 | 7 条表单未触发；3 条运输中确认；1 条多候选误写 |
| 工具不匹配 | 9 | 售后/物流/催件 |
| `handoff` 缺失 | 2 | 无订单超期、custom |
| `confirm` 缺失 | 1 | `c-s015` 运输中退款确认 |

### 工具失败

- `a-s003` / `a-s033`：售后进度，没有 `query_order` / `query_after_sales`
- `a-s039` / `b-s024` / `b-s028`：政策/状态组合
- `b-s010` / `b-s011` / `c-s013`：物流问题，没有 `query_logistics`
- `c-s032`：催件，没有 `urge_logistics`

### 脚本

- 表单未触发：`a-c009`、`b-c005/6/9`、`c-c005/6/7`
- 运输中确认：`c-c001/c002/c004`
- 多候选误写：`a-c004`

## 下一步

1. 工具链 9 条
2. 运输中脚本 3 条
3. 脚本表单 7 条
4. 再跑 v1.1，稳定后再做 v2
