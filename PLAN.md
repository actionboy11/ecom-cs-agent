# 电商售后客服 Agent —— 4 周项目计划

> 目标：4 周内产出一个「能演示、能报数、能讲透」的 Agent 项目，并完成投递；拿到 Agent 开发岗 offer。
> 约束：Java 背景 / Python 入门 / 每周 36 小时（6h × 6 天）/ 4 周后投递 / 暂不考虑大平台 Infra 与算法岗。
> 定位：中厂（及小厂）的「AI Agent 应用开发 / 大模型应用开发（客服·电商方向）」岗位。

---

## 1. 岗位定位（已定）

| 项 | 结论 | 依据 |
|---|---|---|
| 岗位类型 | AI Agent 应用开发 / 大模型应用开发（客服·电商） | 中厂 JD 高频：场景落地 + 全栈交付 |
| 不投 | 平台 Infra、Agent Runtime 内核、算法/训练 | 学历与背景门槛高，且非本次目标 |
| 差异化 | Java 后端 × Python Agent：Agent 通过 MCP 操作真实业务系统 | 小红书/滴滴 JD 明确要 Java + Spring Cloud + MQ；多数转行者无后端深度 |
| 城市/公司 | 中厂优先（电商、OTA、本地生活、SaaS、AI 应用公司） | — |

---

## 2. 项目定义

**一句话**：售后客服 Agent 工作台——用户用自然语言描述售后诉求，Agent 完成意图识别、知识检索、订单/物流/退款工具调用、多轮澄清、人工转接，并沉淀可复盘的会话轨迹与评测指标。

**业务闭环**：进线 → 意图识别 → 知识/工具 → 处理（查询/催件/退款申请）→ 转人工（必要时）→ 结束 → 轨迹回流评测集。

**技术内核**：LangGraph 状态机 + checkpointer 断点续跑 + interrupt 人工审核 + subgraph 多 Agent + MCP 工具接入 + 评测/可观测。

### 2.1 架构

```
用户 (Streamlit / CLI)
        │
        ▼
[Python Agent 服务: FastAPI + LangGraph]
  ├── 主图: intent → (knowledge | tool) → respond → (handoff?)
  ├── subgraph: 查询Agent / 处理Agent / 复核Agent
  ├── Checkpointer: SQLite(会话状态，断点续跑)
  ├── Memory: 短期(会话) + 长期(用户画像, 退换货偏好)
  └── Tools: MCP client ──────────┐
                                  ▼
                    [Java Spring Boot 业务系统: 订单/物流/退款 + 审计日志]
                                  │
                    [MySQL]  [MCP Server (Spring AI MCP)]
        │
        ▼
[评测 & 可观测: 评测集(60条) + 规则Grader + LLM Judge + Trace(JSONL) + Streamlit 看板]
```

### 2.2 技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| Agent 编排 | LangGraph（StateGraph / subgraph / checkpointer / interrupt / stream） | 面试深挖主战场 |
| 组件层 | LangChain（tool binding、structured output、retriever、callbacks） | 明确要求“熟悉 LangChain” |
| 服务 | FastAPI + Pydantic v2 + uv | Python 现代工程化 |
| 业务系统 | Java 17 + Spring Boot 3 + Maven + MyBatis/JPA + MySQL | 复用既有 Java 资产 |
| 工具协议 | MCP（Spring AI MCP Server + Python MCP client） | JD 高频，且能体现 Java↔Python 集成 |
| 检索 | Chroma（本地）+ bge-m3 / text-embedding | 轻量，够用 |
| 观测 | 自建 Trace：LangChain callbacks → JSONL/SQLite → Streamlit | 不依赖付费平台，可讲清实现 |
| 部署 | Docker Compose（mysql + java + python + ui） | 一键启动 |
| 模型 | 待定（见「待确认」），走 OpenAI 兼容协议 | 便于切换 |

### 2.3 LangGraph 必须亲手做的四件事（面试考点）

1. **checkpointer**：会话中断后用 `thread_id` 恢复，演示“服务重启不丢会话”。
2. **interrupt**：转人工——图挂起 → 人工在 UI 确认 → 恢复继续。
3. **subgraph**：查询/处理/复核 三个子图，展示多 Agent 分工与状态传递。
4. **stream**：逐节点流式输出，前端展示“Agent 正在做什么”。

---

## 3. 4 周排期（36h/周，日粒度）

> 节奏：每天 2.5h 学 + 2.5h 做 + 1h 写文档/复盘。每周六必须有一次“可演示”产出。

### W1（36h）地基：Python 工程化 + LangChain/LangGraph + 首个端到端

| 天 | 内容 | 交付物 |
|---|---|---|
| D1 | 环境与骨架：uv、FastAPI、目录、.env、日志；Python 工程化速成（typing/pydantic/async/pytest） | 跑起来的空服务 + 仓库规范 |
| D2 | LangChain：Runnable/LCEL、tool binding、structured output、retriever、callbacks | 3 个最小实验脚本 |
| D3 | LangGraph：StateGraph、条件边、checkpointer、stream | 一个“意图→工具→应答”的玩具图 |
| D4 | Java 侧：Spring Boot 3 个接口（订单/物流/退款）+ 审计日志 + MCP Server 暴露 | 可 curl 的 Java 服务 + MCP 工具可列 |
| D5 | 主图 v1 接入真实工具；造 10 条工单样例 | 端到端跑通 1 条链路 |
| D6 | 联调 + 失败重试 + Bug 清单 + 周复盘 | W1 演示（录屏 1 分钟） |

### W2（36h）业务闭环：记忆、多轮、转人工、多 Agent

| 天 | 内容 | 交付物 |
|---|---|---|
| D1 | 会话状态设计：thread_id、State 字段、短期记忆 | 状态图 + 字段说明 |
| D2 | 多轮澄清与槽位填充（订单号/退款原因/商品） | 5 轮对话不崩 |
| D3 | interrupt 转人工 + 恢复 + 审计 | 转人工全流程录屏 |
| D4 | subgraph 多 Agent：查询/处理/复核 | 多 Agent 协作演示 |
| D5 | 工具治理：权限、幂等、超时、重试、降级 | 工具失败仍能兜底 |
| D6 | 评测集扩到 40 条 + Trace 埋点 + 周复盘 | W2 演示 + 40 条 case |

### W3（36h）评测与优化：从“能跑”到“能报数”

| 天 | 内容 | 交付物 |
|---|---|---|
| D1 | 评测体系设计：60 条 case（正常/边界/对抗） | cases.jsonl + 标注规范 |
| D2 | 规则 Grader：意图、工具、完成率、合规 | grader.py + 单测 |
| D3 | LLM Judge：话术质量与幻觉判定 | judge + 抽样校准 |
| D4 | 优化轮 1：Prompt、上下文压缩、检索策略 | before/after 对比表 |
| D5 | 优化轮 2：模型路由、缓存、延迟与成本 | 成本/延迟对比 |
| D6 | Streamlit 看板（指标 + Trace 浏览）+ 周复盘 | 可展示的指标看板 |

### W4（36h）交付与求职

| 天 | 内容 | 交付物 |
|---|---|---|
| D1 | Docker Compose 一键启动 + README + 架构图 | 新机器 10 分钟可跑 |
| D2 | Demo 视频（3–5 分钟）+ 技术文章初稿 | 视频 + 文章 |
| D3 | 简历两版（Agent 应用 / Java+AI）+ STAR 拆解 | 简历定稿 |
| D4 | 面试题库 30 问 + 8 个深挖点（checkpointer/interrupt/subgraph/eval/降级/成本/安全/记忆） | 问答手册 |
| D5 | 试水投递 10 家 + 模拟面试 | 投递记录 |
| D6 | 缓冲补漏 + 全量投递（目标 20–30 家）+ 复盘 | 投递清单 |

---

## 4. 验收指标（写进简历的数字来源）

**业务指标**
- 一次解决率（未转人工即闭环）
- 转人工率
- 平均对话轮次
- 平均处理时长（模拟）

**技术指标**
- 意图识别准确率
- 工具调用准确率（选对工具 + 参数正确）
- 任务完成率
- P95 延迟
- 单会话 token 成本
- 工具失败恢复率

> 目标：至少 3 个指标有优化前/后对比，且能在面试里解释“怎么测的、为什么提升”。

---

## 5. 交付物清单

- [ ] 可运行项目（Docker Compose 一键启动）
- [ ] README：架构图、快速开始、设计取舍
- [ ] 评测报告（指标 + 失败案例分析）
- [ ] Demo 视频 3–5 分钟
- [ ] 技术文章 1 篇（发在掘金/知乎，作为作品背书）
- [ ] 简历两版 + 面试问答手册

---

## 6. 风险与红线

| 风险 | 应对 |
|---|---|
| 前松后紧，第 4 周才发现跑不完 | 每周六强制演示；未达标的下周优先补 |
| 变成“又一个 RAG demo” | 必须有工具调用 + 多轮 + 转人工 + 评测四件套 |
| 只调 API，讲不出原理 | 每个 LangGraph 机制都写一段“我踩的坑” |
| 用 Java 写 Agent 内核 | Agent 内核必须 Python，Java 只做业务系统与 MCP |
| 没有失败案例 | 保留坏 case 分析，面试最加分 |
| 只顾项目不顾投递 | 第 4 周 D5 必须开始投，不能无限打磨 |

---

## 7. 待确认（影响脚手架）

1. **模型 API**：用哪家？（DeepSeek / 通义 / OpenAI / 本地 Ollama）——决定 base_url 与 key 配置。
2. **Java 环境**：本机 JDK 版本、Maven 是否可用？（计划用 Java 17 + Maven）
3. **Docker**：本机是否已装 Docker Desktop？（影响 W4 一键启动方案，没装则降级为本地进程 + 脚本）
4. **前端**：Streamlit 够用，还是要一个简单 React 页面？（界面主要给 demo 用）

---

## 8. 下一步

1. 确认第 7 节 4 个问题 → 生成项目脚手架。
2. W1-D1：环境跑通 + 骨架提交第一个 commit。
3. 每天结束时在 `docs/daily/` 记录 3 行：做了什么、卡在哪、明天做什么。
