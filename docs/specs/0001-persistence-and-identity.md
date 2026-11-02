# 规格 0001 · 数据与身份基座（切片 1）

> 状态：待评审 ｜ 目标：把「内存 demo」变成「有边界的最小系统」
> 上游文档：[SPEC](../SPEC.md) · [术语表](../../GLOSSARY.md) · [ADR-0001](../../docs/adr/0001-unauthorized-returns-404.md) · [ADR-0002](../../docs/adr/0002-mysql-for-business-sqlite-for-agent-state.md)

---

## Problem Statement

现在这个系统“能演示，但不可信”：

- 业务数据存在内存里，重启就回到初始状态，演示和评测都无法复现；
- 没有身份概念——任何人只要在对话里报出一个订单号，就能查到别人的订单与物流；
- 没有登录、没有角色，坐席与买家的能力完全一样。

拿这样的项目去投递，面试官看第一眼就会归类为“又一个 demo”。

## Solution

把业务事实落到 MySQL（Flyway 版本化迁移 + 可复现种子），引入基于 JWT 的身份与 `CUSTOMER` / `CS_AGENT` 两种角色，并对每一份资源做归属校验：越权访问统一返回 **404** 并写一条 `DENIED` 审计。

完成后，系统具备三条可验证的性质：**重启不丢业务数据**、**只能看自己的东西**、**越权行为有记录**。

## User Stories

1. 作为买家，我想用账号密码登录并拿到一个令牌，这样后续请求不需要每次带密码。
2. 作为买家，我想在令牌有效期内连续操作，而不必反复登录。
3. 作为买家，令牌过期后我想收到明确的“需要重新登录”信号，而不是含糊的错误。
4. 作为买家，我只想看到自己的订单列表，不想看到别人的订单混进来。
5. 作为买家，我想按订单号查自己的订单详情，并看到商品、金额、状态与下单时间。
6. 作为买家，我想查自己订单的物流轨迹，并按时间顺序看到每个节点。
7. 作为买家，当我输入一个不属于自己的订单号时，我想得到“未查询到该订单”的回应，而不是“无权限”这种会泄露“该订单存在”的信息。
8. 作为买家，我不想因为自己的订单号被猜中而让别人看到我的收货信息。
9. 作为坐席，我想看到所有买家的订单，以便处理跨用户的售后问题。
10. 作为坐席，我想在处理越权投诉时查看审计记录，确认谁在什么时候尝试访问了别人的资源。
11. 作为坐席，我希望买家无法调用只有坐席能用的接口。
12. 作为开发者，我想用一条命令起 MySQL 并自动建表与灌入种子数据，而不是手工执行 SQL。
13. 作为开发者，我想让种子数据可重复执行且结果一致，方便重置演示环境。
14. 作为开发者，我想让表结构演进有版本记录，未来加字段不用手工改库。
15. 作为开发者，我想在本地跑测试时验证“越权被拦住”，而不依赖手工点界面。
16. 作为开发者，我想让密码以 BCrypt 哈希存储，而不是明文或可逆加密。
17. 作为开发者，我想让测试在真实 MySQL 语义下运行（而不是内存数据库），避免“测试全绿、上线建表失败”。
18. 作为评审者，我想看到清晰的表结构与字段含义，以判断设计是否合理。
19. 作为评审者，我想看到“越权返回 404”的一致行为，而不是不同接口返回不同状态码。
20. 作为评审者，我想确认审计记录里不包含对话正文，只包含操作元数据。
21. 作为未来的维护者，我想知道为什么业务数据放 MySQL、会话状态却放 SQLite。
22. 作为未来的维护者，我想在迁移脚本里看到 4 个演示账号、6 个商品、12 笔订单的完整定义，而不是散落在代码里。

## Implementation Decisions

**数据模型**

- 新增 6 张表：`users`、`products`、`orders`、`logistics`、`logistics_traces`、`audit_logs`。字段与约束以 [SPEC 第 5.2 节](../SPEC.md) 为准。
- 归属关系外键化：`orders.user_id`、`after_sales_requests.user_id`（本切片先建 `orders`）。查询必须在 SQL 层带 `user_id` 条件，坐席分支除外。
- `products.attrs` / `faq` 用 JSON 列；`logistics_traces` 独立成表以支持按时间排序。
- 种子数据：4 个账号（3 买家 + 1 坐席）、6 个商品、**12 笔订单**（3 买家各 4 单）、每单 1 条物流 + 3–5 条轨迹。

**迁移**

- 使用 Flyway，`V1__init.sql` 建表，`V2__seed.sql` 灌业务种子。
- 用户种子**不放 SQL**：密码哈希由应用启动时用 `PasswordEncoder` 生成并幂等写入，避免在迁移里硬编码哈希。
- 迁移必须可重复应用到空库；`flyway.baseline-on-migrate` 打开以兼容已有库。

**身份与鉴权**

- JWT（HS256），载荷含 `sub`（用户名）、`userId`、`role`，有效期 **2 小时**，无 refresh。
- 登录接口 `POST /api/auth/login` 返回 `{token, role, displayName, userId}`；失败一律 401，不区分“用户不存在”与“密码错误”。
- 使用无状态 `OncePerRequestFilter` 解析 Bearer 令牌并填充 `SecurityContext`；不使用 session。
- 密码用 BCrypt 存储。

**越权行为**（遵循 [ADR-0001](../adr/0001-unauthorized-returns-404.md)）

- 资源不属于当前用户 → 返回 **404**，响应体与“资源不存在”完全一致。
- 同时写 `audit_logs`，`result='DENIED'`，`detail` 记录请求路径与资源 ID，**不记录对话正文**。
- 角色不满足（如买家调用坐席接口）→ 403。

**接口契约**

- 保留现有 4 个查询接口的路径与响应结构不变：`GET /api/orders`、`GET /api/orders/{orderNo}`、`GET /api/logistics/{orderNo}`、`GET /api/products/{sku}`。
- `GET /api/products/{sku}` 保持公开（商品信息不属个人数据）。
- 新增 `POST /api/auth/login` 与 `GET /api/audit`（后者仅 CS_AGENT）。
- 存储层从内存实现替换为 MyBatis-Plus Mapper，**接口层签名不变**。

**刻意不做**

- 不做 refresh token、注册、找回密码、登出黑名单。
- 不做多租户、行级安全策略（RLS）。

## Testing Decisions

**什么是好测试**：只断言外部可观察行为——HTTP 状态码、响应体关键字段、审计记录是否存在；不断言内部方法调用次数、不 mock 数据库。

**最高缝合点（seam）**：Java 的 **HTTP 接口层**，用 `@SpringBootTest` + `MockMvc` 打通「过滤器 → 控制器 → 服务 → 数据库」整条链路。这是本切片唯一的测试缝，避免为每个类单独造缝。

**数据库**：优先 Testcontainers MySQL（真实语义，能验证 Flyway 与 ENUM/JSON 列）；若演示机 Docker 不可用，退化为“compose 起 MySQL + 测试 profile 指向它”，但该退化必须在测试文档里标注。

**测试清单（先红后绿）**

| 用例 | 期望 |
|---|---|
| 正确账号密码登录 | 200 + 返回 token/role |
| 错误密码 / 不存在用户 | 401，且两者响应体一致 |
| 无 token 访问订单 | 401 |
| 过期/伪造 token | 401 |
| 买家查自己的订单 | 200 + 订单字段 |
| 买家查他人订单 | 404 + 审计出现 `DENIED` |
| 买家查他人物流 | 404 + 审计出现 `DENIED` |
| 坐席查任意订单 | 200 |
| 买家列表只含自己的订单 | 200 + 数量与归属断言 |
| 买家调用 `/api/audit` | 403 |
| 商品查询不带 token | 200 |

**现有缝合点**：Python 侧 `pytest`（节点级）与本切片无关，不改动；其用例作为回归基线保持全绿。

**验收命令**：`mvn -q verify` 全绿；手工 `curl` 清单见规格末尾。

## Out of Scope

- 售后请求统一建模与审批接口（切片 2）
- SQLite checkpointer、`thread_owner`、TTL 清理（切片 3）
- Chroma 检索与引用（切片 4）
- MCP 工具化（切片 5）
- 三层评测与拒答边界（切片 6）
- Streamlit 双栏界面、Docker 全栈编排（切片 7）
- 真实支付/物流对接、微调、React 前端

## Further Notes

**切片计划**（每片独立可验收，不合并执行）

| 切片 | 内容 | 依赖 |
|---|---|---|
| 1 | 本规格：MySQL + 迁移 + 种子 + JWT + 归属校验 | — |
| 2 | `after_sales_request` 建模 + 审批接口 | 1 |
| 3 | SQLite checkpointer + thread_owner + TTL | 1 |
| 4 | Chroma 全意图检索 + `[P0x]` 引用 | 3 |
| 5 | MCP 工具化（含身份注入） | 1 |
| 6 | 三层评测 + 拒错边界 + 错误码 | 2、4、5 |
| 7 | Streamlit 双栏 + compose 全栈 + 录屏 | 6 |

**手工验收清单（本切片）**

```bash
# 1. 起库
docker compose up -d mysql

# 2. 起服务（Flyway 自动建表 + 种子）
cd java-service && mvn spring-boot:run

# 3. 登录
curl -s -X POST localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"buyer_a","password":"demo123"}'

# 4. 用返回的 token 查自己的订单（应 200）
curl -s localhost:8080/api/orders/CS2024001 -H "Authorization: Bearer <token_a>"

# 5. 换 buyer_b 的 token 查同一个订单（应 404）
curl -s localhost:8080/api/orders/CS2024001 -H "Authorization: Bearer <token_b>"

# 6. 坐席查审计（应能看到 DENIED）
curl -s localhost:8080/api/audit -H "Authorization: Bearer <token_agent>"
```
