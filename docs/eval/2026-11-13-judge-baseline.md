# LLM judge 第二轨基线（2026-11-13，holdout）

## 为什么要第二轨

第一轨是子串匹配（`must_contain`）：便宜、确定，但只能证明「事实要点出现过」，不能证明「用户的问题被解决了」。
第二轨用 LLM 判断是否解决，专门抓「要点齐全但答非所问」。

## 口径与命令

```bash
# holdout = 每 5 条抽 1 条（--holdout 0.2），共 12 条
uv run python -m eval.run_eval \
  --cases eval/business_cases.jsonl \
  --split holdout --holdout 0.2 \
  --judge --json > docs/eval/2026-11-13-judge-holdout.json
```

- judge 模型：`settings.model_reasoning`（本次 `deepseek-chat`），温度 0
- judge 只判 `chain=llm` 的回复；模板兜底跳过（ADR-0003）
- judge 看**完整回复**与 `tool_result` 业务数据，不看截断版本
- 失败/无 Key 时标 `judge_failed`/`judge_skipped`，不伪造 0 分

## 结果（holdout 12 条）

| 指标 | 值 |
|---|---|
| 用例 | 12（holdout） |
| 子串回复符合率（第一轨） | **75.0%（9/12）** |
| LLM judge 解决率（第二轨） | **66.7%（8/12）** |
| 判定失败 | 0 |
| 模板兜底跳过 | 0 |
| judge 模型 | `deepseek-chat` |

未解决 4 条：

| id | 输入（截断） | judge 理由 |
|---|---|---|
| b01 | 帮我查一下订单 CS2024001 | 要求用户补充手机尾号核验身份，未直接解决查询 |
| b06 | CS2024009 这个订单怎么回事 | 未查到记录，仅让核对后重试 |
| b26 | 我要退款（未给单号） | 要求提供订单号，未实际创建售后 |
| b46 | 我要投诉 | 只转人工，未给任何实际处理或安抚方案 |

两轨差 1 条（b06）：子串认为「没有找到对应的记录」符合预期话术，judge 认为用户问题没被解决。
差距比早先 20 条非 holdout 抽样（85% vs 60%）小，说明**小样本波动很大**，不应引用单次数字当结论。

## 与 SPEC 目标的关系

SPEC 的业务集目标是「回复符合率 ≥85%」。当前 holdout：第一轨 75%、第二轨 66.7%，**均未达标**。
本基线的作用是暴露问题，不是证明达标。

## 诚实边界

1. **judge 是模型判模型**，没有人工一致性校验（校招项目取舍，面试可主动说明）
2. **样本 12 条**，置信区间很宽；扩大样本成本线性增长
3. 部分「未解决」是产品策略：查询需核验身份、催件需满足条件；judge 按「是否解决」一律判未解决，调优前要先定口径
4. judge 走 `reasoning` 模型：`fast` 任务可能配置到另一个供应商（本次 Qwen Key 不可用会 401）
5. 报告里两轨并列，不允许只报高的那一轨；原始结果见 [judge-holdout.json](2026-11-13-judge-holdout.json)
