# 三层评测：2026-11-13

## 数据来源（必须先读）

| 层 | 用例 | 来源 | 说明 |
|---|---|---|---|
| 标准 | 600 条（抽样 100） | **本地等效用例** | 公开的 600 条售后基准未随仓库分发、离线无法下载。`eval/standard_cases.jsonl` 由 `eval/gen_standard_cases.py` 确定性生成，**不是公开集**；真正接入公开集用 `eval/public_bench.py --source <jsonl>` |
| 业务 | 60 条 | 自建 | `eval/business_cases.jsonl` |
| 安全 | 4 条越权 + 9 条拒答 | 自建 | `eval/security_check.py` / `eval/safety_cases.jsonl` |

## 命令

```bash
python -m eval.run_all --standard-limit 100   # 三层一起跑，报告写入 eval/reports/
python -m eval.security_check                # 4 条越权 + audit_log DENIED 校验
python -m eval.public_bench --source <path>  # 公开集适配器（不内置数据）
python -m eval.gen_standard_cases            # 重新生成 600 条等效用例
```

## 结果（后端在线）

| 层 | 用例 | 意图准确率 | 工具成功率 | 回复符合率 | 引用命中 |
|---|---|---|---|---|---|
| 标准（等效用例抽样） | 100 | 100% | 82.0% | 78.0% | — |
| 业务 | 60 | 100% | 98.3% | 81.7% | 100%（8/8） |
| 安全：越权 | 4 | — | 拦截 4/4（100%） | — | — |
| 安全：拒答 | 9 | 100% | — | 100% | — |

- 越权检查同时核对 `audit_log`：命中 **10 条 DENIED** 记录（资源号匹配 4 条目标）
- 拒答分类：越权 2/2、竞品 2/2、闲聊 2/2、违规 3/3
- 标准层工具成功率偏低（82%）：等效用例里含无库存 SKU 与不存在的订单，属预期失败，不是链路问题

## 诚实边界

1. **没有跑公开 600 条**：只跑了本地等效用例，报告与 README 均标注 `local-equivalent`；
2. 公开集接入代码已就绪（`eval/public_bench.py`），需要自行下载数据后执行；
3. 业务集回复符合率在多次运行间有波动（81.7%–88.3%），原因是 LLM 生成非确定性；意图与工具指标稳定。
