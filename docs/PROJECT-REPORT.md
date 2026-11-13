# 电商售后客服 Agent · 项目总报告

> 版本：v1.0（对应 SPEC v4 冻结设计）｜更新：2026-11-02
> 用途：项目全景文档——技术选型、功能实现、数据设计、接口契约、评测与排期。
> 阅读顺序建议：第 1 节（是什么）→ 第 4 节（怎么做）→ 第 6 节（数据怎么存）。

---

## 1. 项目概述

**一句话**：一个双栏客服 Agent 工作台——买家侧对话，坐席侧审批；AI Agent 通过 MCP 操作真实的 Java + MySQL 业务系统；资源级鉴权；三层可复现评测。

**解决什么问题**：市面上大量的「AI 客服 demo」只演示成功路径。真实系统里真正难的是四件事——**越权访问、写操作出错、工具挂掉、以及怎么证明效果**。本项目把重心放在这四件事上。

**五个演示场景**：查物流、申请售后（含审批）、投诉转人工、商品咨询、越权拦截。

**目标岗位**：AI Agent 开发 / 大模型应用开发（校招）。项目定位是「能讲透的工程作品」，不是功能大而全的产品。

---

## 2. 技术选型

| 层 | 技术 | 版本 | 选它的理由 |
|---|---|---|---|
| Agent 编排 | **LangGraph** | ≥0.2.60 | checkpointer / interrupt / subgraph 是面试硬考点；状态机语义比链式调用清晰 |
| 组件层 | **LangChain** | ≥0.3 | tool binding、structured output、retriever、callback 生态 |
| 模型接入 | langchain-openai（OpenAI 兼容） | — | 一套代码切换 DeepSeek / 千问 / Ollama |
| 主模型 | **DeepSeek-chat** | — | 中文工具调用稳定、成本低 |
| 降级模型 | 千问 qwen-turbo | — | 主模型不可用时切换 |
| 本地模型 | Ollama `qwen3:8b` | — | 离线演示、轻任务（改写/压缩） |
| Embedding | Ollama `bge-m3` | 1024 维 | 本地免费、中文效果好、无需 API Key |
| 向量库 | Chroma | — | 嵌入式、零运维，适合单机项目 |
| Agent 服务 | FastAPI + Pydantic v2 + uvicorn | — | 异步、类型安全、自带 OpenAPI |
| 业务系统 | **Spring Boot 3.5.5 / JDK 21** | — | 复用 Java 能力，形成跨语言集成叙事 |
| 持久层 | MyBatis-Plus + **Flyway** | — | 迁移可版本化、可复现种子数据 |
| 鉴权 | **Spring Security + JJWT + BCrypt** | — | 标准方案，角色 + 资源双重校验 |
| 工具协议 | **MCP**（Spring AI MCP Server ↔ Python client） | — | JD 高频；且能体现「跨语言工具化」 |
| 会话状态 | **SQLite**（langgraph-checkpoint-sqlite） | — | 高频小写入，与业务数据分离 |
| 前端 | **Streamlit** | — | 6 小时能出双栏工作台；React 留到投递后 |
| 部署 | Docker Compose | — | 一键起 MySQL + Java + Python + UI |
| 可观测 | 自建 Trace（JSONL） | — | 60 行实现，面试能讲清「自己怎么造的」 |
| 测试 | pytest | — | 无 Key 也能跑（分类/兜底有单测） |

**不选什么**：React（时间成本）、微调（校招不考）、K8s（过度）、LangSmith（自建更可讲）、CI（时间黑洞）。

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│ Streamlit（双栏：买家对话 / 坐席审批 + Trace）                │
└───────────────┬─────────────────────────────────────────────┘
                │ HTTP + JWT
┌───────────────▼─────────────────────────────────────────────┐
│ Python: FastAPI                                              │
│  ├─ LangGraph 状态机（classify → tools/knowledge/handoff）    │
│  ├─ Checkpointer（SQLite）：会话续跑 + thread 归属             │
│  ├─ Chroma 检索（政策 12 条，全意图检索）                       │
│  ├─ MCP Client（工具调用，user_id 服务端注入）                 │
│  └─ Trace(JSONL) + 评测脚本                                   │
└───────────────┬─────────────────────────────────────────────┘
                │ MCP（stdio / SSE）
┌───────────────▼─────────────────────────────────────────────┐
│ Java: Spring Boot 3.5.5                                      │
│  ├─ Spring Security + JWT（2h）                               │
│  ├─ 订单 / 物流 / 售后请求 / 商品 / 审计                       │
│  ├─ 资源归属校验（越权 → 404 + DENIED 审计）                   │
│  └─ Flyway 迁移 + MyBatis-Plus                               │
└───────────────┬─────────────────────────────────────────────┘
                │ JDBC
           MySQL 8.4（业务事实）
```

**为什么是 Java + Python 双栈**：Agent 内核用 Python（生态与岗位要求），业务系统用 Java（复用既有积累 + 证明跨语言集成能力）。同类开源项目里几乎没有人做这件事。

---

## 4. 功能实现（逐项）

| 功能 | 入口 | 处理链 | 落库/留痕 | 失败处理 |
|---|---|---|---|---|
| **登录** | `POST /api/auth/login` | BCrypt 校验 → 签发 JWT（2h，含 role/userId） | `audit_logs(LOGIN)`：只记 username 与结果，失败原因统一 `credentials`；不记密码/令牌 | 401，不区分「用户不存在/密码错」 |
| **查订单** | `GET /api/orders/{no}` | JWT 解析 user_id → 归属校验 → MyBatis 查询 | `audit_logs(QUERY_ORDER)` | 非本人 → **404** + `DENIED` 审计 |
| **订单列表** | `GET /api/orders` | 买家查自己；坐席查全部 | 审计 | 401 |
| **查物流** | `GET /api/logistics/{no}` | 归属校验 → 物流 + 轨迹（子查询） | 审计 | 同订单 |
| **申请售后** | `POST /api/after-sales` | 归属校验 → 类型（退款/退货/换货）→ 政策校验 → 插入 PENDING | `after_sales_requests` + 审计 | 订单不存在/非本人 → 404 |
| **坐席审批** | `POST /api/after-sales/{no}/review` | 校验角色 CS_AGENT → 更新状态 + reviewed_by/at | 状态 + 审计 | 非坐席 → 403 |
| **商品查询** | `GET /api/products/{sku}`、`?keyword=` | SKU 直查 / 名称模糊 | **不写审计**（公开只读，无身份主体） | 未找到 → 404 |
| **政策问答** | Agent 内部 | query → bge-m3 → Chroma top-3 → 阈值 0.35 → 拼上下文 + `[P0x]` | trace 记录命中片段 | 无命中 → 明确说「政策未覆盖」+ 转人工 |
| **意图分类** | Agent 节点 `classify` | LLM 结构化输出（7 类 + 槽位）；失败降级关键词 | trace | 降级不报错，标注 `source=keyword` |
| **工具调用** | Agent 节点 `tools` | 按意图分发 4 个工具；user_id 由 State 注入 | trace + Java 审计 | **错误码分流**（见 4.1） |
| **转人工** | `handoff_prepare → await_human` | 先写摘要与回复入 State → checkpoint → `interrupt()` 挂起 → 恢复后继续 | checkpoint + 审计 | 恢复失败 → 保持挂起 |
| **拒答** | Agent 节点 `refuse` | 四类（越权/竞品/无关/违规）→ 标准话术 | trace | — |
| **多轮上限** | Agent 节点 | `turn_count > 10` → 强制转人工 | trace | — |
| **TTL 清理** | 启动 + 每日 + CLI | 删除过期 `checkpoints`/`writes`/`thread_owner`/`traces` | 物理删除 | `--dry-run` 预览 |

### 4.1 工具错误码（替代自由文本）

| 码 | 触发 | Agent 行为 |
|---|---|---|
| `NOT_FOUND` | 资源不存在 | 告知未找到 + 建议核对单号 |
| `DENIED` | 非本人资源 | 与 NOT_FOUND 同口径；审计 DENIED |
| `UNAUTHORIZED` | token 失效 | 提示重新登录 |
| `UNAVAILABLE` | 业务系统 5xx | 重试一次 → 转人工 |
| `TIMEOUT` | 超时 | 重试一次 → 转人工 |
| `MISSING_SLOT` | 缺订单号/SKU | 追问槽位 |
| `INVALID_INPUT` | 参数非法 | 澄清并重试 |

### 4.2 Agent 图

```
START → classify ─┬─ product_info ───────────→ tools → respond
                  ├─ order_query/logistics/after_sales → tools → respond
                  ├─ policy ───────────────────→ respond（引用政策）
                  ├─ complaint → handoff_prepare → await_human(interrupt) → respond
                  ├─ refuse → respond（标准话术）
                  └─ turn>10 → respond（转人工兜底）
```

**State 字段**：`thread_id, user_id, role, messages[], intent, order_no, sku, as_type, reason, confidence, tool_result, error_code, knowledge, policy_refs[], needs_human, handoff_approved, reply, turn_count`

**三个必须讲清的机制**：
1. **checkpointer**：每个节点执行后落 State 快照，按 `thread_id` 恢复 → 服务重启不丢会话。
2. **interrupt**：挂起前必须先把回复写进 State（`handoff_prepare`），否则恢复后用户看到空回复。
3. **user_id 注入**：工具参数里没有 `user_id`，由服务端从 JWT/State 注入 → 模型无法伪造身份。

---

## 5. 接口清单

| 方法 | 路径 | 角色 | 说明 |
|---|---|---|---|
| POST | `/api/auth/login` | 公开 | 返回 JWT |
| GET | `/api/health` | 公开 | 健康检查 |
| GET | `/api/products/{sku}` | 公开 | 商品详情 |
| GET | `/api/products/search?keyword=` | 公开 | 商品搜索 |
| GET | `/api/orders` | CUSTOMER / CS_AGENT | 买家仅自己 |
| GET | `/api/orders/{no}` | CUSTOMER / CS_AGENT | 非本人 404 |
| GET | `/api/logistics/{no}` | CUSTOMER / CS_AGENT | 非本人 404 |
| POST | `/api/after-sales` | CUSTOMER | 创建 PENDING |
| POST | `/api/after-sales/{no}/review` | CS_AGENT | 通过 / 驳回 |
| GET | `/api/audit?limit=` | CS_AGENT | 审计列表 |
| POST | `/api/v1/chat` | 登录用户 | 对话（含 thread_id） |
| POST | `/api/v1/chat/stream` | 登录用户 | SSE 流式 |
| POST | `/api/v1/threads/{id}/resume` | 登录用户 | 审批后恢复 |
| GET | `/api/v1/health` | 公开 | Agent + 依赖连通性 |

---

## 6. 数据库设计

### 6.1 设计原则

1. **业务事实进 MySQL，可丢状态进 SQLite**（ADR-0002）。
2. **归属外键化**：`orders.user_id`、`after_sales_requests.user_id` 是权限校验的根，查询强制带条件。
3. **审计不存对话正文**：只记谁、对什么、做了什么、结果如何（ADR-0001）。
4. **状态用 ENUM 而非布尔**：`PENDING/APPROVED/REJECTED` 可扩展。

### 6.2 表结构

```sql
users(id BIGINT PK AI, username VARCHAR(50) UNIQUE, password_hash VARCHAR(100),
      role ENUM('CUSTOMER','CS_AGENT'), display_name VARCHAR(50), created_at DATETIME)

products(sku VARCHAR(20) PK, name VARCHAR(100), price DECIMAL(10,2),
         attrs JSON, stock INT, faq JSON)

orders(order_no VARCHAR(20) PK, user_id BIGINT, sku VARCHAR(20), item_name VARCHAR(100),
       amount DECIMAL(10,2), status VARCHAR(20), created_at DATETIME, INDEX idx_user(user_id))

logistics(order_no VARCHAR(20) PK, carrier VARCHAR(50), tracking_no VARCHAR(50), status VARCHAR(20))

logistics_traces(id BIGINT PK AI, order_no VARCHAR(20), seq INT,
                 trace_time DATETIME, content VARCHAR(200), INDEX idx_order(order_no))

after_sales_requests(request_no VARCHAR(20) PK, order_no VARCHAR(20), user_id BIGINT,
                     type ENUM('REFUND','RETURN','EXCHANGE'), reason VARCHAR(200),
                     status ENUM('PENDING','APPROVED','REJECTED'), created_at DATETIME,
                     reviewed_by VARCHAR(50), reviewed_at DATETIME,
                     INDEX idx_user(user_id), INDEX idx_order(order_no))

audit_logs(id BIGINT PK AI, ts DATETIME, actor VARCHAR(50), actor_role VARCHAR(20),
           action VARCHAR(50), resource_type VARCHAR(20), resource_id VARCHAR(50),
           result ENUM('OK','DENIED'), detail JSON, INDEX idx_ts(ts))
```

### 6.3 关系

```
users 1 ── N orders 1 ── 1 logistics 1 ── N logistics_traces
  │                 │
  │                 └── 1 ── N after_sales_requests
  └── 1 ── N after_sales_requests

products 1 ── N orders（按 sku 关联）
audit_logs 独立表：actor 用字符串，不建外键（可能是系统/SYSTEM 身份）
```

### 6.4 关键设计说明

| 决策 | 理由 |
|---|---|
| `after_sales_requests` 一张表 + `type` | 三类售后共享「校验→创建→审批→更新」流程，分表会让审计与状态机复制三份（ADR-0004） |
| `attrs` 用 JSON | 商品参数随品类变化，建宽表会大量空列；检索不依赖它 |
| `logistics_traces` 单独表 | 一对多，避免 JSON 数组无法按时间查询/排序 |
| `audit_logs.resource_id` 存字符串 | 审计要能跨资源类型（订单/售后请求/线程），不强绑外键 |
| 不建 `sessions` 表 | 会话状态在 SQLite，MySQL 只存业务事实 |

### 6.5 SQLite（Agent 侧）

```
checkpoints / writes      LangGraph 官方表
thread_owner(thread_id PK, user_id, created_at, updated_at)
```

**TTL**：会话相关数据 30 天（`SESSION_TTL_DAYS`）物理删除；审计 365 天且不含正文（ADR-0005）。

---

## 7. 权限与安全

| 机制 | 实现 |
|---|---|
| 认证 | JWT（HS256，2h），无 refresh |
| 授权 | 角色（CUSTOMER/CS_AGENT）× 资源归属双层校验 |
| 越权响应 | 统一 404，不泄露资源存在性，审计记 `DENIED` |
| 身份注入 | 工具签名不含 `user_id`；由服务端从 JWT/State 注入 |
| 数据层兜底 | 查询 SQL 强制 `where user_id=?`（坐席例外） |
| 会话越权 | `thread_owner` 校验，非本人 thread → 404 |
| 拒答 | 四类边界 + 标准话术 |

---

## 8. 评测体系

| 层 | 数据 | 规模 | 判定 | 指标 | 通过线 |
|---|---|---|---|---|---|
| 标准 | 公开售后基准（csnewerst） | 600 | oracle 工具轨迹比对 | 任务完成率 | ≥70% |
| 业务 | 自建 `business_cases.jsonl` | 60（48 train / 12 holdout） | 子串判事实 + LLM judge 判是否解决 | 意图/工具/事实/judge | ≥85% |
| 安全 | `security_cases.jsonl` | 4 | 必须拒绝且不含他人信息 | 拦截率 | 100% |
| 质量 | CSConv 抽样 | 200 | 人工核验 20 条 | 策略匹配 | 定性 |

**双轨判定的分工**：子串负责「不许幻觉」（单号/金额必须在），judge 负责「是否真的解决了」。分开报分，不混成一个分数。

**纪律**：train 调优 / holdout 验收；关键词规则冻结、不计入质量指标（ADR-0003）；报告必须标注数据集与链路来源。

---

## 9. 部署与运行

| 服务 | 镜像/进程 | 端口 | 依赖 |
|---|---|---|---|
| mysql | mysql:8.4 | 3308（宿主机）→ 3306（容器） | — |
| java-service | 多阶段构建（maven → jre21） | 8080 | mysql |
| python-agent | python:3.12-slim | 8000 | java |
| ui | streamlit | 8501 | python |

**环境变量**：`DEEPSEEK_API_KEY`、`QWEN_API_KEY`、`OLLAMA_BASE_URL`、`MODEL_*`、`BUSINESS_API_BASE`、`SESSION_TTL_DAYS`、`MYSQL_*`。

**本地开发**：MySQL 用 compose 起，Java/Python 直接跑（热更新）；一条命令 `docker compose up` 起全栈。

---

## 10. 目录结构

```
├── java-service/                 # Spring Boot 业务系统
│   ├── src/main/java/com/example/csagent/
│   │   ├── api/                  # 控制器 + 异常处理
│   │   ├── domain/               # Order / Product / AfterSalesRequest
│   │   ├── store/                # 数据访问（→ MyBatis-Plus）
│   │   ├── security/             # JWT 过滤器（待建）
│   │   └── mcp/                  # MCP Server（待建）
│   └── src/main/resources/db/migration/   # Flyway（待建）
├── python-agent/
│   ├── app/
│   │   ├── graph/                # state / nodes / builder
│   │   ├── llm/                  # 多模型注册与路由
│   │   ├── tools/                # 业务客户端 + MCP client
│   │   ├── rag/                  # Chroma 检索（待建）
│   │   ├── observability/        # trace
│   │   ├── maintenance/          # TTL 清理（待建）
│   │   └── api/                  # FastAPI 路由
│   ├── eval/                     # 用例 + 评测脚本
│   └── ui/                       # Streamlit（待建）
├── data/policies/                # 政策库（12 条）
├── docs/                         # SPEC / ADR / 简历 / 每日记录
└── docker-compose.yml
```

---

## 11. 关键设计取舍（ADR 摘要）

| # | 决策 | 一句话理由 |
|---|---|---|
| 0001 | 越权返回 404 而非 403 | 403 泄露资源存在性，可被枚举 |
| 0002 | 业务数据 MySQL / 会话状态 SQLite | 事实不可丢、状态可丢，生命周期不同 |
| 0003 | 关键词规则冻结、不计入质量指标 | 参与评测就会变成「自己出题自己考」 |
| 0004 | 售后请求统一建模 | 三类共享流程，分表让审计与状态机复制三份 |
| 0005 | 会话 30 天 TTL，审计 365 天 | 会话含个人信息可删，追责记录不可删 |

---

## 12. 当前实现状态

| 模块 | 状态 |
|---|---|
| LangGraph 图（分类/工具/知识/转人工两段式） | ✅ 已实现（含 7 个单测） |
| 多模型路由（DeepSeek/千问/Ollama + 降级） | ✅ 已实现 |
| **JWT 鉴权 + 资源归属校验 + 越权 404 + 审计** | ✅ 已实现（切片 1） |
| **MySQL + Flyway + 种子数据（4 用户 / 6 商品 / 12 订单）** | ✅ 已实现（切片 1） |
| **订单 / 物流 / 商品查询改读 MySQL** | ✅ 已实现（切片 1） |
| **`/api/audit` 改读数据库，仅坐席可访问** | ✅ 已实现（切片 1） |
| 退款接口（内存版，已加归属校验） | ⚠️ 待切片 2 迁移到 `after_sales_requests` |
| 60 条业务用例 + 评测脚本 + holdout | ✅ 已实现 |
| 政策库 12 条 + 规格书 + ADR + 词汇表 | ✅ 已实现 |
| SQLite checkpointer + thread_owner + TTL | ⏳ 切片 3 |
| Chroma 全意图检索 + 引用 | ⏳ 切片 4 |
| MCP 工具化 | ⏳ 切片 5 |
| 拒答四类 / 错误码 / 10 轮上限 | ⏳ 切片 6 |
| 双轨评测报告 | ⏳ 切片 6 |
| Streamlit 双栏 | ⏳ 切片 7 |
| 部署 + 录屏 + 投递 | ⏳ 切片 7 |

---

## 13. 六周路线图

| 周 | 主线 | 验收 |
|---|---|---|
| W1 | MySQL + JWT + 归属校验 + 售后建模 + 会话持久化 | 越权 4/4、重启续聊、TTL 生效 |
| W2 | Chroma + MCP | 政策带引用、MCP 三工具通 |
| W3 | 三层评测 + 拒答 + 错误码 | 双轨报告 + 公开集跑分 |
| W4 | Streamlit + compose + README | 一键启动 + 5 分钟录屏 + 投递 5 家 |
| W5 | subgraph 多 Agent + 多模型成本矩阵 | 三模型对比 |
| W6 | 文章 + 模拟面试 + 投递 30 家 | 投递记录 |

---

## 14. 已知风险

| 风险 | 影响 | 兜底 |
|---|---|---|
| Spring AI MCP 与 Boot 3.5.5 不兼容 | W2 阻塞 | 48h 内切 Python FastMCP |
| 公开 600 条集工具签名差异 | 适配成本 | 映射层适配，超 48h 先用自建集 |
| DeepSeek 限流 | 评测耗时 | 并发限制 + 重试 |
| 无实习 + 学历不占优 | 简历关 | 项目作品 + 公开仓库 + 持续投递 |

---

## 15. 演示脚本（5 分钟）

1. **登录** `buyer_a` → 展示 JWT 与角色
2. **S1 查物流**：问「耳机到哪了」→ 追问订单号 → 给号 → 回复含运单号 + 轨迹 + `[P04]`
3. **S2 申请退款**：说明尺码不合适 → 创建 PENDING → 切 `cs_agent` 审批通过 → 状态回写
4. **S3 投诉**：情绪话术 → 转人工挂起 → 恢复
5. **S4 商品咨询**：无 SKU 问「耳机续航多久」→ 搜索 → 回答
6. **S5 越权**：`buyer_a` 报 `buyer_b` 订单 → 统一 404 → 坐席面板显示「累计拦截 N 次」
