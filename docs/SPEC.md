# 项目规格书 v4（设计冻结）

> v4 相对 v3 的变化（本轮 7 项决策）：
> ① 售后请求统一建模 `after_sales_request`（REFUND/RETURN/EXCHANGE）
> ② 角色 `AGENT` → `CS_AGENT`（避免与 AI Agent 混淆）
> ③ 工具错误升级为错误码枚举，分类型处理
> ④ 所有应答前统一检索 top-3，命中才引用（不再仅限 policy 意图）
> ⑤ 新增商品搜索接口，去掉 SKU 硬编码映射
> ⑥ 拒答边界分四类，各一句标准话术
> ⑦ 评测双轨：子串判事实 + LLM judge 判是否解决

---

## 1. 目标与验收

**一句话**：双栏客服 Agent 工作台——买家侧对话，坐席侧审批；Agent 通过 MCP 操作真实 Java + MySQL 业务系统；资源级鉴权；三层可复现评测。

**v1 完成标准**
- [ ] 五个演示场景可重复演示（录屏 5 分钟）
- [ ] 三层评测 + 越权 4 条 + 双轨判定报告
- [ ] `docker compose up` 一把起（MySQL + Java + Python + UI）
- [ ] README 中英双版 + 架构图 + 设计取舍 + GLOSSARY 链接

---

## 2. 角色与权限

| 角色 | 说明 | 账号（密码 `demo123`） |
|---|---|---|
| `CUSTOMER` | 买家，只能访问自己的资源 | `buyer_a` / `buyer_b` / `buyer_c` |
| `CS_AGENT` | 坐席，可读全部，写操作需审批 | `cs_agent` |

| 资源 / 操作 | CUSTOMER | CS_AGENT | 未登录 |
|---|---|---|---|
| `GET /api/products/{sku}`、`/api/products/search` | ✅ | ✅ | ✅ |
| `GET /api/orders` | 仅自己 | 全部 | 401 |
| `GET /api/orders/{no}` | 仅自己，否则 **404** | ✅ | 401 |
| `GET /api/logistics/{no}` | 仅自己，否则 **404** | ✅ | 401 |
| `POST /api/after-sales` | 仅自己订单 | 403 | 401 |
| `POST /api/after-sales/{no}/review` | 403 | ✅ | 401 |
| `GET /api/after-sales` | 仅自己 | 全部 | 401 |
| `GET /api/audit` | 403 | ✅ | 401 |
| `POST /api/v1/chat` | 仅自己的 thread，否则 **404** | 403（坐席不能接管买家对话） | 401 |
| `POST /api/v1/chat/stream` | 同 `/chat` | 403 | 401 |
| `POST /api/v1/threads/{id}/resume` | 404（无恢复权限，按越权处理） | ✅ 任意 thread 的待审转接（审批是坐席职责） | 401 |

> **说明**：`/chat` 允许首次创建 thread，因此 404 只表示「已存在但无权」；`thread_id` 由客户端生成、不是敏感标识，这个信息量可接受。`resume` 仅坐席可用，买家调用与不存在/无权同样返回 404，并写 `DENIED` 审计。

**三条安全原则**：身份不可由模型决定；越权统一 404 + `DENIED` 审计；数据层强制 `user_id` 过滤。

---

## 3. 五个演示场景

| # | 场景 | 链路 | 技术点 |
|---|---|---|---|
| S1 查物流 | 缺单号 → 追问 → 查物流 → 轨迹 + 超 72h 提示 | 多轮、工具、知识 |
| S2 申请售后 | 判断类型（退款/退货/换货）→ 查订单 → 校验政策 → 创建 PENDING → 坐席审批 → 回写 | 写操作、HITL、审计 |
| S3 投诉 | 情绪关键词 → 转人工（先落盘再挂起）→ 恢复；错误单号 → 降级 | 容错、interrupt |
| S4 商品咨询 | 有 SKU 直查 / 无 SKU 搜索 → 回答 + 关联政策 | 工具、检索 |
| S5 越权 | 报他人订单号 → 404 → 审计 DENIED → 坐席侧显示拦截次数 | 资源鉴权、防枚举 |

---

## 4. 功能矩阵

| 能力 | v1（W1–4） | v2（W5–6） | 不做 |
|---|---|---|---|
| 权限 | JWT + 归属校验 + 越权 404 + 审计 | 审批面板打磨 | SSO / 多租户 |
| 存储 | MySQL（业务）+ SQLite（Agent 状态） | 索引优化 | 分库分表 |
| 编排 | LangGraph 单图 + checkpointer + interrupt | subgraph 三子图 | 复杂层级 |
| 工具 | 订单、物流、售后请求、商品（经 MCP） | 写操作幂等 | 真实支付/物流 |
| 售后 | 申请（退款/退货/换货 → PENDING）+ **列表**（买家自己的 / 坐席全部）+ 坐席审批 | 审批面板打磨、批量处理 | 真实打款/寄回物流 |
| 知识 | Chroma + 12 条政策 + 全意图检索 + 引用编号 | 混合检索 + 重排 | 知识图谱 |
| 安全 | 拒答四类 + 10 轮上限 + 情绪关键词 | — | 风控平台 |
| 记忆 | 会话短期（SQLite checkpoint）+ 30 天 TTL | 跨会话用户偏好（v2） | 长期知识库 |
| 评测 | 子串 + LLM judge 双轨 + 越权 + holdout | 多模型成本矩阵 | 在线 A/B |
| 界面 | Streamlit 登录 + 双栏 | 细节打磨 | React |

---

## 5. 数据模型

### 5.1 存储划分

业务数据 → **MySQL**；Agent 运行状态（checkpoint、thread 归属）→ **SQLite**。理由见 [ADR-0002](docs/adr/0002-mysql-for-business-sqlite-for-agent-state.md)。

### 5.2 MySQL 表（Flyway `V1__init.sql` / `V2__seed.sql`）

```sql
users(id BIGINT PK AUTO_INCREMENT, username VARCHAR(50) UNIQUE, password_hash VARCHAR(100),
      role ENUM('CUSTOMER','CS_AGENT'), display_name VARCHAR(50), created_at DATETIME)

products(sku VARCHAR(20) PK, name VARCHAR(100), price DECIMAL(10,2),
         attrs JSON, stock INT, faq JSON)

orders(order_no VARCHAR(20) PK, user_id BIGINT, sku VARCHAR(20), item_name VARCHAR(100),
       amount DECIMAL(10,2), status VARCHAR(20), created_at DATETIME, INDEX idx_user(user_id))

logistics(order_no VARCHAR(20) PK, carrier VARCHAR(50), tracking_no VARCHAR(50), status VARCHAR(20))

logistics_traces(id BIGINT PK AUTO_INCREMENT, order_no VARCHAR(20), seq INT,
                 trace_time DATETIME, content VARCHAR(200), INDEX idx_order(order_no))

-- 售后请求：退款 / 退货 / 换货 统一建模
after_sales_requests(request_no VARCHAR(20) PK, order_no VARCHAR(20), user_id BIGINT,
                     type ENUM('REFUND','RETURN','EXCHANGE'), reason VARCHAR(200),
                     status ENUM('PENDING','APPROVED','REJECTED'), created_at DATETIME,
                     reviewed_by VARCHAR(50), reviewed_at DATETIME,
                     INDEX idx_user(user_id), INDEX idx_order(order_no))

audit_logs(id BIGINT PK AUTO_INCREMENT, ts DATETIME, actor VARCHAR(50), actor_role VARCHAR(20),
           action VARCHAR(50), resource_type VARCHAR(20), resource_id VARCHAR(50),
           result ENUM('OK','DENIED'), detail JSON, INDEX idx_ts(ts))
```

### 5.3 种子数据

- 用户：3 买家 + 1 坐席（BCrypt）
- 商品：6 SKU（跑步鞋、耳机、行李箱、保温杯、背包、充电宝）
- 订单：**12 单**（3 买家各 4 单，覆盖四种状态）
- 物流：每单 1 条 + 3–5 条轨迹
- 售后请求：1 条 PENDING（演示审批）

### 5.4 SQLite

`checkpoints` / `writes`（LangGraph 官方）+ `thread_owner(thread_id PK, user_id, created_at, updated_at)`

### 5.5 数据保留与 TTL

| 数据 | 位置 | 保留期 | 清理方式 |
|---|---|---|---|
| `checkpoints` / `writes`（会话状态） | SQLite | **30 天**（`SESSION_TTL_DAYS` 可配） | 定时任务物理删除 |
| `thread_owner`（会话归属） | SQLite | 随对应 thread 一并删除 | 同上 |
| `traces/*.jsonl`（运行轨迹） | 文件 | **30 天** | 按日期删除过期文件 |
| `audit_logs`（业务审计） | MySQL | **365 天** | 只记操作与结果，不存对话正文 |
| 订单 / 售后请求 / 用户 | MySQL | 不自动删除 | 业务事实，按合规要求保留 |

**原则**：会话是「可丢状态」，业务事实是「不可丢数据」。清理时**物理删除**（不软删），因为会话里可能含订单号、地址片段等个人信息。

**触发方式**：① 服务启动时跑一次 ② 每日定时（`APScheduler` 或系统计划任务）③ 提供手动 CLI `python -m app.maintenance.cleanup --dry-run`。


---

## 6. 接口契约

### 6.1 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | `{username,password}` → `{token, role, displayName, userId}` |
| 其余 | — | `Authorization: Bearer <jwt>`，有效期 2h，无 refresh |

### 6.2 业务接口

| 方法 | 路径 | 角色 | 说明 |
|---|---|---|---|
| GET | `/api/health` | 公开 | 健康检查 |
| GET | `/api/products/{sku}` | 公开 | 商品详情 |
| GET | `/api/products/search?keyword=` | 公开 | 按名称搜索（替代 SKU 硬编码） |
| GET | `/api/orders` | CUSTOMER/CS_AGENT | 买家仅自己 |
| GET | `/api/orders/{no}` | CUSTOMER/CS_AGENT | 非本人 404 + DENIED |
| GET | `/api/logistics/{no}` | CUSTOMER/CS_AGENT | 同上 |
| POST | `/api/after-sales` | CUSTOMER | `{orderNo, type, reason}` → PENDING |
| POST | `/api/after-sales/{no}/review` | CS_AGENT | `{approved, note}` |
| GET | `/api/after-sales?status=` | CUSTOMER / CS_AGENT | 买家仅自己；坐席全部；可按状态过滤（切片 2） |
| GET | `/api/audit?limit=` | CS_AGENT | 审计列表 |
| POST | `/api/internal/audit` | 内部服务（`X-Internal-Token`） | 仅接受 `THREAD_ACCESS / THREAD / DENIED`，detail 只含 `reason`；path 必须 `/api/v1/` 开头；未配置令牌一律 401 |

### 6.3 Agent 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/chat` | `{message, thread_id?}` + Bearer |
| POST | `/api/v1/chat/stream` | SSE |
| POST | `/api/v1/threads/{id}/resume` | 坐席审批后恢复 |
| GET | `/api/v1/handoffs` | 坐席查看转接待办（扫描最近会话的 interrupt，只返回元数据） |
| GET | `/api/v1/health` | 含 Java/MySQL 连通性 |

---

## 7. 工具契约与错误码

### 7.1 工具

| 工具 | LLM 可见参数 | 服务端注入 |
|---|---|---|
| `query_order` | `order_no` | `user_id`, `role` |
| `query_logistics` | `order_no` | `user_id`, `role` |
| `create_after_sales_request` | `order_no`, `type`, `reason` | `user_id`, `role` |
| `get_product_info` | `sku` 或 `keyword` | — |

### 7.2 错误码（取代自由文本）

| 码 | 触发 | Agent 行为 |
|---|---|---|
| `NOT_FOUND` | 资源不存在 | 告知未找到 + 建议核对单号 |
| `DENIED` | 非本人资源 | 与 NOT_FOUND 同口径回复；审计记 DENIED |
| `UNAUTHORIZED` | token 失效 | 提示重新登录 |
| `UNAVAILABLE` | 业务系统 5xx | 重试一次 → 转人工 |
| `TIMEOUT` | 超时 | 重试一次 → 转人工 |
| `MISSING_SLOT` | 缺订单号/SKU | 追问槽位 |
| `INVALID_INPUT` | 参数非法 | 澄清并重试 |
| `BAD_REQUEST` | 请求体校验失败 / 非法枚举值 | 提示修正后重试 |
| `CONFLICT` | 资源状态不允许该操作（如重复审批） | 提示当前状态，不重试；**具体状态码不在本 SPEC 约定**（实现取 409） |

---

### 7.3 审计动作清单

所有审计只记「谁 / 对哪个资源 / 做了什么 / 结果」与请求路径，**不记对话正文、密码、令牌**（ADR-0005）。

| action | 触发 | 状态 |
|---|---|---|
| `QUERY_ORDER` | 查订单详情（成功或越权） | ✅ 已实现 |
| `QUERY_ORDER_LIST` | 查订单列表 | ✅ 已实现 |
| `QUERY_LOGISTICS` | 查物流 | ✅ 已实现 |
| `APPLY_AFTER_SALES` | 发起售后申请 | ✅ 已实现（落库） |
| `QUERY_AFTER_SALES_LIST` | 查询售后列表 | ✅ 已实现 |
| `REVIEW_AFTER_SALES` | 坐席审批售后申请 | ✅ 已实现 |
| `READ_AUDIT` | 坐席读取审计 | ✅ 已实现 |
| `THREAD_ACCESS` | Agent 侧会话越权（他人 thread） | ✅ 已实现（内部审计接口上报） |
| `LOGIN` | 登录成功 / 失败 | ✅ 已实现 |

**会话保留（§5.5）补充约定**：没有归属记录的遗留会话（升级前产生、已被访问控制拒绝）无法判定活跃时间，因此**不按 TTL 等待，在任何一次清理中直接删除**；它们已不可访问，保留只会占用空间。

**`LOGIN` 的额外约束**（切片 6 实现时必须遵守）：
- 只记 `username` 与结果，**不记密码、不记令牌**；
- 失败审计不得区分「用户不存在」与「密码错误」，否则审计接口本身成为账号枚举渠道；
- 不记录 IP 与 UA（演示项目无此必要，且会增加 PII 面）。

---

## 8. Agent 流程

```
START → classify → route:
  ├─ product_info → tools(get_product_info) → respond
  ├─ order_query / logistics / after_sales → tools → respond
  ├─ policy → respond(引用政策)
  ├─ complaint → handoff_prepare → await_human(interrupt) → respond
  ├─ refuse(越权/竞品/无关/违规) → respond(标准话术)
  └─ turn_count > 10 → handoff_prepare → await_human(interrupt) → respond(转人工兜底)
```

> 拒答优先于轮次上限：拒答不调用模型/工具，不需要提前转人工。轮次上限走**真实挂起**（与投诉同一套 `handoff`），坐席可通过 `/resume` 恢复。

检索：**每个需要生成回复的节点前**执行 `retrieve(query, top_k=3)`，相似度 ≥ 0.35 才把政策片段拼进上下文，回复末尾附 `[P0x]`。

State：`thread_id, user_id, role, messages[], intent, order_no, sku, as_type, reason, confidence, tool_result, error_code, knowledge, policy_refs[], needs_human, handoff_approved, refusal, reply, turn_count`

---

## 9. 拒答边界（四类）

| 类别 | 触发示例 | 标准话术 |
|---|---|---|
| 越权 | "帮我查别人订单" | "我这边只能处理您本人订单的问题哦～" |
| 竞品比较 | "你们和 XX 比怎么样" | "我只负责售后问题，具体对比建议参考官方参数页。" |
| 无关闲聊 | "今天天气如何" | "我是售后客服，可以帮您查订单、物流或办理售后。" |
| 违规请求 | 索要他人隐私、代写作业等 | "这个我没法帮您，我们继续处理售后问题吧。" |

---

## 10. 评测体系（双轨）

| 层 | 数据 | 判定 | 指标 | 通过线 |
|---|---|---|---|---|
| 标准 | 公开 600 条 | oracle 工具轨迹比对 | 任务完成率 | ≥70% |
| 业务 | 60 条（48 train / 12 holdout） | **子串判事实 + LLM judge 判是否解决** | 意图/工具/事实/judge | ≥85% |
| 安全 | 越权 4 条 | 必须拒绝且不含他人信息 | 拦截率 | 100% |
| 质量 | CSConv 抽样 200 | 人工核验 20 条 | 策略匹配 | 定性 |

**judge 定义**：`deepseek-chat`，温度 0，提示词要求输出 `{solved: bool, reason}`；与子串分**分开报分**（子串=不幻觉，judge=真解决）。
**纪律**：train 调优 / holdout 验收；关键词规则冻结；报告标注数据集与链路（LLM 或兜底）。

---

## 11. UI 线框

```
┌──────────────────────────────────────────────────────────────┐
│ 登录：buyer_a / buyer_b / buyer_c / cs_agent      [登录]      │
├───────────────────────────┬──────────────────────────────────┤
│ 买家对话（左）             │ 坐席面板（右，CS_AGENT 可见）     │
│ ┌───────────────────────┐ │ 待审批：AS20260001 退款 PENDING   │
│ │ 用户：耳机到哪了？     │ │ 摘要：买家申请退款-尺码不合适     │
│ │ Agent：请提供订单号   │ │ [通过] [驳回]                    │
│ │ 用户：CS2024002       │ │ 累计拦截越权：3 次 ▾ 审计列表     │
│ │ Agent：中通…[P04]     │ │ ▾ Trace 时间线                   │
│ └───────────────────────┘ │                                  │
│ [输入框……………] [发送]     │                                  │
└───────────────────────────┴──────────────────────────────────┘
```

---

## 12. 六周排期与验收

| 周 | 主线 | 验收 |
|---|---|---|
| W1 | MySQL + Flyway + 种子数据；JWT；归属校验；`after_sales_request` 建模；**SQLite checkpointer + `thread_owner` + TTL 清理** | 越权 4/4 拦截；带/不带 token 行为正确；重启后会话可续；过期会话被清理 |

> **实施说明（2026-11-03）**：W1 被拆成三个可独立验收的切片执行——
> 切片 1（MySQL + JWT + 归属校验 + 审计）已完成；
> 切片 2 承接 `after_sales_request` 建模、售后列表与审批流；
> 切片 3 承接 SQLite 会话与 TTL。
> 因此在切片 2、3 关闭前，**W1 整体不算完成**（当前 3/5）。
> 登录审计（`LOGIN`）不属 W1，归入切片 6（安全与评测）。
| W2 | Chroma + 全意图检索 + 引用；MCP 工具化 | 政策问答带 `[P0x]`；MCP 3 工具通 |
| W3 | 三层评测 + 拒答四类 + 错误码 + 10 轮上限 | 双轨报告 + 公开集跑分 |
| W4 | Streamlit 双栏 + compose + README；**投递 5 家** | 一键启动 + 5 分钟录屏 |
| W5 | subgraph 多 Agent + 多模型成本矩阵 | 三模型对比表 |
| W6 | 技术文章 + 模拟面试 + 投递 30 家 | 投递记录表 |

---

## 13. 风险与降级

| 风险 | 降级 |
|---|---|
| Spring AI MCP 版本不兼容 | 48h 内切 Python FastMCP，Java 留 REST |
| MySQL 迁移拖慢进度 | 表结构先冻结，接口不变，只换实现 |
| 权限改造影响评测 | 评测脚本一次性加 token |
| 时间不足 | 砍 v2 的 subgraph 与成本矩阵 |
