# 评测基线：2026-11-10（MCP 工具化后）

命令（Java 业务系统在线）：

```bash
BUSINESS_API_BASE=http://localhost:8181 \
  uv run python -m eval.run_eval --cases eval/business_cases.jsonl --json
```

结果（60 条业务用例）：

| 指标 | 数值 |
|---|---|
| 意图准确率 | 100%（60/60） |
| 工具成功率 | 98.3%（59/60） |
| 回复符合率 | 86.7%（52/60） |
| 引用命中率（回答正文） | 100%（8/8） |
| 检索命中率（主依据） | 100%（8/8） |
| 转人工用例 | 8 |
| 平均耗时 | 1143 ms |

说明：

- 工具调用全部经 MCP（`POST /mcp`），身份由评测账号 JWT 透传；
- 唯一失败的工具用例为缺槽位场景（追问路径），不影响 MCP 链路；
- 引用类指标在 8 条政策用例上计算，报告同时区分「回答引用」与「检索主依据」。

## 安全用例（2026-11-13 追加）

```bash
BUSINESS_API_BASE=http://localhost:8181 \
  uv run python -m eval.run_eval --cases eval/safety_cases.jsonl --json
```

9 条（越权 3、诱导编造 2、超范围 2、敏感信息 2）：**回复符合率 100%（9/9）**，意图 100%。

拒答与工具错误路径改为**模板直出**（不经过 LLM 改写），保证同一错误措辞确定、不泄露资源存在性。
