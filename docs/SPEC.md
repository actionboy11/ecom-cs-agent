# 项目规格书 v3（待签字）

> v3 相对 v2 的变化：**新增权限与鉴权体系**、**MySQL 从第一天开始**、**演示数据扩容至 4 用户 / 12 订单 / 6 商品**、**新增第五个演示场景（越权）**、**新增拒答边界与多轮上限**、**明确 MCP 身份注入规则**。

---

## 0. 签字确认项（勾选即冻结）

- [ ] 权限矩阵（第 2 节）
- [ ] 五个演示场景（第 3 节）
- [ ] 数据模型与 MySQL 迁移（第 5 节）
- [ ] 接口契约与鉴权规则（第 6 节）
- [ ] MCP 身份注入规则（第 7 节）
- [ ] 评测口径（第 10 节）
- [ ] 六周排期与验收（第 13 节）

---

## 1. 目标与验收

**一句话**：双栏客服 Agent 工作台——买家侧对话，坐席侧审批；Agent 通过 MCP 操作真实 Java + MySQL 业务系统；资源级鉴权；三层可复现评测。

**v1 完成标准**：
- [ ] 五个演示场景可重复演示（录屏 5 分钟）
- [ ] 三层评测报告（公开 600 / 业务 60 / 质量 1,855 抽样）
- [ ] 越权用例全部拦截且留审计
- [ ] `docker compose up` 一把起（MySQL + Java + Python + UI）
- [ ] README 中英双版 + 架构图 + 设计取舍

---

## 2. 权限矩阵（核心新增）

### 2.1 角色

| 角色 | 说明 | 登录账号（密码统一 `demo123`） |
|---|---|---|
| `CUSTOMER` | 买家，只能访问自己的资源 | `buyer_a` / `buyer_b` / `buyer_c` |
| `AGENT` | 坐席，可读全部资源，写操作需审批 | `cs_agent` |

### 2.2 权限矩阵

| 资源 / 操作 | CUSTOMER | AGENT | 未登录 |
|---|---|---|---|
| 商品信息 `GET /api/products/{sku}` | ✅ | ✅ | ✅（公开） |
| 订单列表 `GET /api/orders` | 仅自己 | 全部 | ❌ 401 |
| 订单详情 `GET /api/orders/{no}` | 仅自己，否则 **404** | ✅ | ❌ 401 |
| 物流 `GET /api/logistics/{no}` | 仅自己，否则 **404** | ✅ | ❌ 401 |
| 申请退款 `POST /api/refunds` | 仅自己的订单 | ❌ 403（必须由买家发起） | ❌ 401 |
| 审批退款 `POST /api/refunds/{no}/approve` | ❌ 403 | ✅ | ❌ 401 |
| 审计日志 `GET /api/audit` | ❌ 403 | ✅ | ❌ 401 |
| 会话续聊 `POST /api/v1/chat`（带 thread_id） | 仅自己的 thread，否则 **404** | 自己的 thread | ❌ 401 |

### 2.3 三条安全原则

1. **身份不可由模型决定**：LLM 只能产出业务参数（订单号、原因、SKU），`user_id` 由服务端从 JWT/session 注入，工具签名不暴露。
2. **越权统一 404**：不返回 403，避免通过状态码探测资源是否存在；同时写 `DENIED` 审计。
3. **数据层兜底**：所有查询 SQL 强制带 `user_id` 条件（AGENT 例外），不依赖应用层 if 判断。

---

## 3. 五个演示场景

| # | 场景 | 链路 | 技术点 |
|---|---|---|---|
| S1 查物流 | 缺单号 → 追问 → 查物流 → 轨迹 + 超 72h 提示 | 多轮、工具、知识融合 |
| S2 申请退款 | 查订单 → 校验政策 → 创建 PENDING → 触发审批 → 坐席通过 → 状态回写 | 写操作、HITL、审计 |
| S3 投诉 | 情绪关键词 → 转人工（先落盘再挂起）→ 恢复；错误单号 → 降级 | 容错、interrupt |
| S4 商品咨询 | 问续航/尺码/库存 → 商品工具 → 回答 + 关联政策 | 结构化数据转自然语言 |
| **S5 越权** | `buyer_a` 报 `buyer_b` 的订单号 → 统一 404「未查询到该订单」→ 审计出现 DENIED → 坐席侧显示「累计拦截 N 次」 | **资源级鉴权、防枚举** |

---

## 4. 功能矩阵

| 能力 | v1（W1–4） | v2（W5–6） | 不做 |
|---|---|---|---|
| 权限 | JWT + 资源归属 + 越权 404 + 审计 | 坐席审批面板打磨 | SSO / 多租户 |
| 存储 | **MySQL（业务）+ SQLite（Agent checkpoint）** | 索引与慢查询优化 | 分库分表 |
| 编排 | LangGraph 单图 + checkpointer + interrupt | subgraph 三子图 | 复杂层级 |
| 工具 | 4 个，经 MCP 调 Java | 写操作幂等 | 真实支付/物流 |
| 知识 | Chroma + 12 条政策 + 引用编号 | 混合检索 + 重排 | 知识图谱 |
| 安全 | 拒答边界 + 10 轮上限 + 情绪关键词 | — | 内容风控平台 |
| 记忆 | 会话短期 | 跨会话用户偏好 | 长期知识库 |
| 评测 | 三层 + 越权 4 条 + held-out | 多模型成本矩阵 | 在线 A/B |
| 界面 | Streamlit 登录 + 双栏 | 细节打磨 | React |

---

## 5. 数据模型

### 5.1 为什么 MySQL 从第一天开始

业务数据（用户/订单/退款/审计）是**关系型、需要事务**的，越晚迁移改动越多；Agent 运行状态（checkpoint）是**高频写、结构化程度低**的 KV，放 SQLite 更轻。两者分离是主流做法。

### 5.2 MySQL 表（Flyway `V1__init.sql` / `V2__seed.sql`）

```sql
users(id BIGINT PK AUTO_INCREMENT, username VARCHAR(50) UNIQUE, password_hash VARCHAR(100),
      role ENUM('CUSTOMER','AGENT'), display_name VARCHAR(50), created_at DATETIME)

products(sku VARCHAR(20) PK, name VARCHAR(100), price DECIMAL(10,2),
         attrs JSON, stock INT, faq JSON)

orders(order_no VARCHAR(20) PK, user_id BIGINT, sku VARCHAR(20), item_name VARCHAR(100),
       amount DECIMAL(10,2), status VARCHAR(20), created_at DATETIME,
       INDEX idx_user(user_id))

logistics(order_no VARCHAR(20) PK, carrier VARCHAR(50), tracking_no VARCHAR(50), status VARCHAR(20))

logistics_traces(id BIGINT PK AUTO_INCREMENT, order_no VARCHAR(20), seq INT,
                 trace_time DATETIME, content VARCHAR(200), INDEX idx_order(order_no))

refunds(refund_no VARCHAR(20) PK, order_no VARCHAR(20), user_id BIGINT, reason VARCHAR(200),
        status ENUM('PENDING','APPROVED','REJECTED'), created_at DATETIME,
        reviewed_by VARCHAR(50), reviewed_at DATETIME)

audit_logs(id BIGINT PK AUTO_INCREMENT, ts DATETIME, actor VARCHAR(50), actor_role VARCHAR(20),
           action VARCHAR(50), resource_type VARCHAR(20), resource_id VARCHAR(50),
           result ENUM('OK','DENIED'), detail JSON, INDEX idx_ts(ts))
```

### 5.3 种子数据

- 用户：`buyer_a` / `buyer_b` / `buyer_c` / `cs_agent`（密码 `demo123`，BCrypt）
- 商品：6 个 SKU（跑步鞋、耳机、行李箱、保温杯、背包、充电宝）
- 订单：**12 单**（3 个买家各 4 单，覆盖已签收/运输中/已发货/待发货）
- 物流：每单 1 条物流 + 3–5 条轨迹
- 退款：1 条 PENDING（用于演示审批）

### 5.4 Python 侧 SQLite

```
checkpoints / writes      # LangGraph 官方表（langgraph-checkpoint-sqlite）
thread_owner(thread_id PK, user_id, created_at, updated_at)   # 会话归属
```

---

## 6. 接口契约

### 6.1 认证

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| POST | `/api/auth/login` | 无 | `{username, password}` → `{token, role, displayName, userId}` |
| — | 其余接口 | `Authorization: Bearer <jwt>` | JWT 有效期 2h，无 refresh |

### 6.2 业务接口

| 方法 | 路径 | 角色 | 说明 |
|---|---|---|---|
| GET | `/api/health` | 公开 | 健康检查 |
| GET | `/api/products/{sku}` | 公开 | 商品信息 |
| GET | `/api/orders` | CUSTOMER/AGENT | 买家仅自己；坐席全部 |
| GET | `/api/orders/{orderNo}` | CUSTOMER/AGENT | 非本人 → 404 + DENIED 审计 |
| GET | `/api/logistics/{orderNo}` | CUSTOMER/AGENT | 同上 |
| POST | `/api/refunds` | CUSTOMER | 仅本人订单；创建 PENDING |
| POST | `/api/refunds/{refundNo}/approve` | AGENT | 通过/驳回 |
| GET | `/api/audit?limit=` | AGENT | 审计列表 |

### 6.3 Agent 接口（Python）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/chat` | `{message, thread_id?}` + Bearer → 返回 reply/intent/tool_result/needs_human |
| POST | `/api/v1/chat/stream` | SSE 逐节点 |
| POST | `/api/v1/threads/{id}/resume` | 坐席审批后恢复 |
| GET | `/api/v1/health` | 含 Java/MySQL 连通性 |

**规则**：`thread_id` 首次出现时绑定当前 `user_id`；他人复用 → 404。

---

## 7. MCP 工具契约与身份注入

| 工具 | 暴露给 LLM 的参数 | 服务端注入 | 说明 |
|---|---|---|---|
| `query_order` | `order_no` | `user_id`, `role` | 归属校验在 Java 侧 |
| `query_logistics` | `order_no` | `user_id`, `role` | 同上 |
| `create_after_sales_request` | `order_no`, `reason` | `user_id`, `role` | 仅 CUSTOMER；创建 PENDING |
| `get_product_info` | `sku` | — | 公开数据 |

**实现方式**：Python 侧 tool wrapper 从 State 取 `user_id` 注入 MCP 调用参数；LLM 的 tool schema 里**不出现** `user_id` 字段。

> 风险：Spring AI MCP Server 与 Boot 3.5.5 的版本兼容。若 48h 内跑不通，降级为 Python 侧 FastMCP server（内部转发 Java REST），Java 仍保留 REST 与鉴权 —— 降级方案同样满足「MCP 工具化」的面试叙事。

---

## 8. Agent 状态与流程

```
START → classify → route:
  ├─ product_info → tools(get_product) → respond
  ├─ order_query / logistics / refund → tools → respond
  ├─ policy → knowledge(Chroma) → respond
  ├─ complaint → handoff_prepare → await_human(interrupt) → respond
  └─ 拒答 / 超 10 轮 → respond(兜底话术)
```

State：`thread_id, user_id, role, messages[], intent, order_no, sku, reason, confidence, tool_result, knowledge, policy_refs[], needs_human, handoff_approved, reply, turn_count`

---

## 9. 知识库与引用

- 源：`data/policies/policies.md` 12 条，按 `##` 分块，metadata `policy_id`
- 检索：`bge-m3` embedding，top-k=3，相似度阈值 0.35
- 回复：末尾附 `[P01]` 形式编号；坐席侧展示命中片段
- 无命中：明确「当前政策未覆盖」→ 转人工，**禁止自由发挥**

---

## 10. 评测体系

| 层 | 数据 | 规模 | 指标 | 通过线 |
|---|---|---|---|---|
| 标准 | csnewerst 600 case（工具名映射适配） | 600 | 任务完成率 | ≥ 70%，不达标也发布 |
| 业务 | `business_cases.jsonl`（48 train / **12 holdout**） | 60 | 意图准确率、工具成功率、回复符合率 | ≥ 85%（holdout 单独报） |
| 越权 | 新增 `security_cases.jsonl` | 4 | 拦截率 | **100%** |
| 质量 | CSConv 抽样 | 200 | 策略匹配（人工核验 20 条） | 定性说明 |

**越权 4 条**：① buyer_a 查 buyer_b 订单 ② 伪造/篡改 token ③ 买家调坐席审批接口 ④ 复用他人 thread_id。

**纪律**：关键词规则冻结，不为评测集改规则；train 调优、holdout 验收；报告标注数据集来源。

---

## 11. UI 线框（Streamlit）

```
┌──────────────────────────────────────────────────────────────┐
│ 登录：buyer_a / buyer_b / buyer_c / cs_agent   [登录]         │
├───────────────────────────┬──────────────────────────────────┤
│ 买家对话（左栏）           │ 坐席面板（右栏，AGENT 可见）      │
│ ┌───────────────────────┐ │ ┌──────────────────────────────┐ │
│ │ 用户：耳机到哪了？     │ │ │ 待审批：RF20260001 (PENDING)  │ │
│ │ Agent：请提供订单号   │ │ │ 摘要：买家申请退款-尺码不合适 │ │
│ │ 用户：CS2024002       │ │ │ [通过] [驳回]                 │ │
│ │ Agent：中通…运单号…   │ │ └──────────────────────────────┘ │
│ └───────────────────────┘ │ 累计拦截越权：3 次 ▾ 审计列表      │
│ [输入框……………] [发送]     │ ▾ Trace 时间线（节点耗时）        │
└───────────────────────────┴──────────────────────────────────┘
```

---

## 12. 目录结构

```
java-service/   Spring Boot + Security/JWT + MyBatis-Plus + Flyway + MCP Server
python-agent/   FastAPI + LangGraph + MCP client + Chroma + SQLite(checkpoint)
  eval/         business_cases.jsonl / security_cases.jsonl / run_eval.py
  ui/           streamlit_app.py
data/policies/  政策库
docs/           SPEC / 简历 / 每日记录
```

---

## 13. 六周排期与验收

| 周 | 主线 | 验收（做不到就砍功能，不延期） |
|---|---|---|
| W1 | **MySQL + Flyway + 种子数据；JWT 鉴权；资源归属校验** | 越权用例 4/4 拦截；curl 带/不带 token 行为正确 |
| W2 | **Chroma + 引用溯源；MCP 工具化（含身份注入）** | 政策问答带 `[P0x]`；MCP 跑通 3 工具 |
| W3 | 三层评测 + 拒答边界 + 10 轮上限 | 60 条 + 4 条越权 + 公开集跑分 |
| W4 | Streamlit 双栏 + docker compose + README；**投递 5 家** | 一键启动；5 分钟录屏 |
| W5 | subgraph 多 Agent + 多模型成本矩阵 | 三模型对比表 |
| W6 | 技术文章 + 模拟面试 + 全量投递 30 家 | 投递记录表 |

---

## 14. 风险与降级

| 风险 | 降级方案 |
|---|---|
| Spring AI MCP 版本不兼容 | 48h 内切 Python FastMCP，Java 留 REST |
| MySQL 迁移拖慢进度 | 表结构先冻结，接口层不变，仅换实现 |
| 权限改造影响现有评测 | 评测脚本同步加 token 参数，一次性改完 |
| 时间不足 | 砍 v2 的多 Agent 与成本矩阵，保 v1 五场景 |
