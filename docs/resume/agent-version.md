# 毛永辉 · 简历（Agent 开发版 v2 草稿）

> 用法：本文件是**可直接复制进简历的改写稿**。`[待填]` 处在项目 v1 完成后替换为真实数字。
> 另一版（Java 后端版）只调整顺序与关键词，内容 90% 相同，见文末「双版本差异」。

---

## 抬头

**毛永辉** ｜ 浙江师范大学 · 电子信息（硕士）· 2027 届
求职意向：**AI Agent 开发工程师 / 大模型应用开发工程师**
GitHub：github.com/actionboy11 ｜ 在线演示：47-76-185-182.sslip.io ｜ 邮箱：2201997603@qq.com ｜ 电话：19101533069

---

## 教育背景

- **浙江师范大学** 电子信息 · 硕士 ｜ 2024.09 – 2027.06
- **南昌大学科学技术学院** 计算机科学与技术 · 学士 ｜ 2020.09 – 2024.06

---

## 专业技能

- **Python 与 Agent 工程**：LangGraph（StateGraph / checkpointer / interrupt / subgraph）、LangChain（Tool / Structured Output / Retriever / Callback）、FastAPI、MCP（Server / Client）、Pydantic、uv；Ollama 本地模型（qwen3:8b）与 bge-m3 向量化
- **Java 与并发**：集合、线程池、synchronized / volatile / CAS / ThreadLocal；JVM 内存模型、对象分配与 G1 回收
- **Spring 生态**：Spring Boot / MVC / Security / MyBatis-Plus；IoC、AOP、Bean 生命周期、事务机制、自动配置
- **AI 应用工程（Java）**：Spring AI 构建 Agent 与 RAG；多模型接入、Tool Calling、结构化输出、Query Rewrite；pgvector / Qdrant 向量检索
- **数据与中间件**：MySQL、PostgreSQL、Redis；RabbitMQ / RocketMQ（手动 ACK、延迟重试、死信队列、消费幂等）

---

## 项目经历

### 1. 电商售后客服 Agent（Python / LangGraph + MCP + Java 业务系统）｜个人项目｜2026.11 – 至今

**技术栈**：Python 3.12、LangGraph、LangChain、FastAPI、MCP、Spring Boot 3 / Java 21、MySQL、Chroma、Ollama、Docker Compose
**开源仓库**：https://github.com/actionboy11/ecom-cs-agent

- 用 LangGraph 编排「意图识别 → 知识检索 / 工具调用 → 应答 → 转人工」状态机，落地 checkpointer 断点续跑（服务重启不丢会话）、interrupt 人工审核后恢复、subgraph 多 Agent 分工三项核心机制。
- Agent 通过 **MCP** 调用 Spring Boot 订单 / 物流 / 退款接口，业务侧实现权限校验、操作审计与写操作幂等；工具失败按「重试 → 备用模型 → 人工转接」三级降级，转人工时把会话上下文摘要推给坐席。
- 构建三层评测：公开 600 条电商售后评测集（10 类售后任务）+ 自建 60 条业务用例（转人工 / 降级 / 权限）+ 1,855 通真实客服对话的策略与共情评测；同一套用例在 DeepSeek / 千问 / 本地 qwen3:8b 上对比「准确率 - P95 延迟 - 单会话成本」。
- **结果**：任务完成率 `[待填]%`，P95 延迟 `[待填]ms`，单会话成本 `[待填]`，较单模型基线降低 `[待填]%`。

### 2. 基于 Spring AI 的智能面试与职业辅导系统｜独立开发｜2026.09 – 至今

**技术栈**：Java 21、Spring Boot、Spring AI、React、PostgreSQL、pgvector、RabbitMQ、Redis、RustFS、Docker Compose

- 构建「简历解析 → JD 分析 → 技能选取 → 个性化出题 → 多轮面试 → 分批评估 → 报告生成」工作流，按需加载 10 类面试技能；基于 Tika + Embedding + pgvector 构建 RAG，实现语义分块、Query Rewrite 与无命中拒答。
- 设计 `LlmProviderRegistry` 统一管理 Chat / Embedding Model 与 Tool Calling，采用缓存容器整体替换避免配置刷新期旧实例并发回填；封装 `StructuredOutputInvoker` 统一 JSON Schema 校验、格式修复、定向重试与 Micrometer 指标。
- 将简历分析、语音评估与知识库向量化迁移至 RabbitMQ：持久化 + 手动 ACK + 10/30/60s 延迟重试 + 消费幂等 + 死信审计，支持失败任务追踪与人工重放。

### 3. 医学影像分析与多角色智能 Agent 平台｜独立开发｜2026.05 – 2026.08

**技术栈**：Java 21、Spring Boot、Spring Security、Spring AI、MyBatis-Plus、MySQL、Redis、RabbitMQ、Vue 3、FastAPI、PyTorch、Qdrant

- 设计 Skill Router → Skill Orchestrator → Native Tool Calling 两阶段架构，支撑医生 / 患者多角色 Agent 的病例筛选、任务查询、队列统计、报告解释与医学知识检索。
- 建立 **180 条自建用例**的 Agent 回归评测（技能路由 / 参数提取 / 多轮上下文 / RAG 引用 / 攻击测试五类），人工校验金标；定向优化后路由准确率 70% → 100%、参数准确率 70% → 100%，并沉淀失败案例集与误判归因。
- 将自研视网膜血管分割模型封装为 FastAPI / PyTorch 推理服务，经 RabbitMQ 异步集成；结合 Publisher Confirm、手动 ACK、失败重试与幂等状态流转完成任务追踪与结果回写。

---

## 科研与成果

- 英文论文 1 篇（第一作者，已投稿）｜ 软件著作权 1 项 ｜ 发明专利 1 项（已公开）
- CET-4 / CET-6 ｜ 一等奖学金 ×1 ｜ 二等奖学金 ×1

---

## 双版本差异（Java 后端版）

| 项 | Agent 版（本文件） | Java 后端版 |
|---|---|---|
| 求职意向 | AI Agent 开发 / 大模型应用 | Java 后端开发（AI 方向） |
| 技能顺序 | Python & Agent 工程 放第一 | Java 与并发 / Spring 生态 放第一 |
| 项目顺序 | 电商 Agent → 面试系统 → 医学平台 | 面试系统 → 医学平台 → 电商 Agent |
| 项目 1 写法 | 突出 LangGraph / MCP / 评测 | 突出「Python 服务与 Java 业务系统集成」 |
| 投递场景 | AI Agent 岗、大模型应用岗 | Java + 大模型混合岗、传统后端岗 |

---

## 面试话术：100% 指标怎么讲（不要狡辩，要坦诚）

> "这 180 条是我自己生成的用例 + 人工校验，不是独立测试集。它在 70% 左右起步，优化到 100%，但这个 100% 有偏差——因为用例分布是我自己定义的。所以我下一个项目改成了公开 600 条评测集 + 自建 60 条业务用例，并且刻意留了 held-out 集合，就是为了避免自己考自己。"

这句话的作用：**把"可能过拟合"的质疑，转成"我知道怎么科学评测"的加分项**。校招面试官最怕的是不知道自己样本有问题的人。
