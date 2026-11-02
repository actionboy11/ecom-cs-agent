# 项目规格书（SPEC v1）

> 本文是**功能边界与验收的唯一定义**。凡本文没写的功能，一律不做；凡本文写了的，v1 必须交付。

---

## 1. 目标与验收

**一句话**：一个浏览器里可演示的售后客服 Agent 工作台——买家侧对话，坐席侧看摘要并审批；Agent 通过 MCP 操作真实 Java 业务系统；后台有可复现的三层评测。

**完成标准（全部满足才算 v1 完成）**

- [ ] 四个演示场景可重复演示，录屏 3–5 分钟
- [ ] 三层评测出报告：公开 600 条 + 自建 60 条 + 质量评测
- [ ] `docker compose up` 一键启动（MySQL + Java + Python + UI）
- [ ] README 含架构图、设计取舍、快速开始（中英双版）
- [ ] 公开仓库，无密钥泄露

---

## 2. 四个演示场景

| # | 场景 | 链路 | 演示的技术点 |
|---|---|---|---|
| S1 | **查物流** | 缺单号 → 追问 → 给单号 → 查物流 → 回复轨迹 + 超 72h 提示 | 多轮追问、工具调用、知识融合 |
| S2 | **申请退款**（写操作） | 说明原因 → 查订单 → 校验政策 → 创建退款(PENDING) → 触发人工审核 → 坐席通过 → 状态回写 | 写操作安全、interrupt、审计 |
| S3 | **投诉**（失败处理） | 情绪激烈 → 转人工（先落盘再挂起）→ 恢复；另一支：错误单号 → 工具报错 → 降级 | 容错、降级、interrupt 时序 |
| S4 | **商品咨询**（新增） | 问参数/尺码/库存/续航 → 调商品工具 → 回答 + 关联政策提示 | 新工具、结构化数据转自然语言 |

---

## 3. 功能矩阵

| 能力 | v1（W1–4） | v2（W5–6） | 不做 |
|---|---|---|---|
| 编排 | LangGraph 单图 + checkpointer(SQLite) + interrupt | subgraph 三子图（查询/处理/复核） | 复杂层级 Agent |
| 工具 | 4 个：订单、物流、退款、商品（经 MCP） | 写操作幂等 + 审批流 | 真实支付/物流 |
| 知识 | Chroma + 12 条政策分块检索 | 混合检索 + 重排 | 知识图谱 |
| 多轮 | 槽位追问（订单号/原因/SKU） | 指代消解 | 语音 |
| 记忆 | 会话短期（checkpoint） | 跨会话用户偏好 | 长期知识库 |
| 转人工 | 两段式 + 摘要推坐席 | 审批面板打磨 | 企业 IM |
| 评测 | 三层 + 失败归因 | 多模型成本矩阵 | 在线 A/B |
| 界面 | Streamlit 双栏 | 细节打磨 | React |
| 部署 | docker compose | 监控面板 | K8s |

---

## 4. 接口契约

### 4.1 Java 业务系统（Spring Boot，端口 8080）

| 方法 | 路径 | 说明 | 返回 |
|---|---|---|---|
| GET | `/api/health` | 健康检查 | `{status, service, orders}` |
| GET | `/api/orders/{orderNo}` | 订单详情 | `{orderNo, item, amount, status, createdAt}` |
| GET | `/api/logistics/{orderNo}` | 物流轨迹 | `{orderNo, carrier, trackingNo, status, traces[]}` |
| POST | `/api/refunds` | 创建退款（PENDING） | `{refundNo, orderNo, reason, status, createdAt}` |
| **GET** | **`/api/products/{sku}`** | **商品信息（新增）** | `{sku, name, price, attrs{}, stock, faq[]}` |
| GET | `/api/audit?limit=` | 审计日志 | `[{ts, action, target, detail}]` |

**约束**：退款写操作必须校验订单存在；所有查询与写操作都要写审计。

### 4.2 Python Agent（FastAPI，端口 8000）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/chat` | 单轮对话，返回 `{reply, intent, tool_result, needs_human, interrupt}` |
| POST | `/api/v1/chat/stream` | SSE 流式，逐节点推送 |
| POST | `/api/v1/threads/{id}/resume` | 人工审核后恢复 `{approved}` |
| GET | `/api/v1/health` | 健康检查（含 Java 连通性） |

### 4.3 MCP 工具（Java 侧 Spring AI MCP Server 暴露）

| 工具名 | 入参 | 出参 |
|---|---|---|
| `query_order` | `order_no` | 订单对象 |
| `query_logistics` | `order_no` | 物流对象 |
| `create_after_sales_request` | `order_no`, `reason` | 退款对象 |
| `get_product_info` | `sku` 或 `keyword` | 商品对象 |

> 命名对齐公开评测集（csnewerst 600 条）的 oracle 工具（`query_order_status` / `check_return_policy` / `create_after_sales_request`），适配层做名称映射。

---

## 5. 数据契约

### 5.1 Agent 状态（LangGraph State）

```python
thread_id, user_id          # 会话标识
messages[]                  # 对话
intent, order_no, sku, reason, confidence   # 分类与槽位
tool_result, knowledge      # 中间结果
needs_human, handoff_approved, handoff_summary  # 人工介入
reply                       # 最终回复
```

### 5.2 评测用例（business_cases.jsonl）

```json
{"id":"b01","input":"…","expect_intent":"logistics","expect_tool":true,
 "must_contain":["ZT9876543210"],"difficulty":"easy","tags":["happy_path"]}
```

### 5.3 Trace（traces/YYYYMMDD.jsonl）

```json
{"ts":"…","thread_id":"…","node":"tools","event":"end","payload":{"elapsed_ms":123,"result":"ok"}}
```

---

## 6. 目录结构

```
python-agent/
  app/agent/graph/      # state / nodes / builder
  app/agent/llm/        # 多模型注册与路由
  app/agent/tools/      # 业务客户端 + MCP client
  app/agent/rag/        # Chroma 检索（v1）
  app/observability/    # trace
  app/api/              # FastAPI 路由
  eval/                 # business_cases.jsonl + run_eval.py + reports/
  ui/                   # Streamlit 双栏
java-service/           # Spring Boot 业务系统 + MCP Server
data/policies/          # 政策库（12 条）
docs/                   # SPEC / 简历 / 每日记录
```

---

## 7. 评测定义

| 层 | 数据 | 指标 | 目标 |
|---|---|---|---|
| 标准层 | csnewerst 600 case | 任务完成率 | ≥ 70%（不达标也发布，写清归因） |
| 业务层 | 自建 60 条 | 意图准确率、工具成功率、回复符合率 | ≥ 85% |
| 质量层 | CSConv 1,855 通 | 策略匹配率（抽样人工核验） | 定性说明 |

**纪律**：公开集与自建集分开报；保留失败案例；不做"自己出题自己考 100%"；至少留 20% 用例作 held-out。

---

## 8. 每周验收点

| 周 | 验收（做不到就砍功能，不延期） |
|---|---|
| W1 | 端到端跑通 1 条链路；Java 4 个接口可 curl |
| W2 | 转人工 + 记忆 + 60 条用例；能跑出业务层指标 |
| W3 | 三层评测报告 + 一轮优化 before/after |
| W4 | Streamlit 双栏 + docker compose + README；**投递 5 家** |
| W5 | subgraph 多 Agent + 多模型成本矩阵 |
| W6 | 技术文章 + 模拟面试 + 全量投递 |

---

## 9. 风险与取舍

- **公开评测集适配超 48h** → 先用自建 60 条，公开集挪到 v2
- **MCP 依赖版本冲突** → 48h 内不通就切 Python 侧 MCP Server（Java 只留 REST）
- **写操作安全** → 一律先 PENDING + 人工确认，不自动 APPROVED
- **不追求高分** → 70% 即发布，归因比分数重要
