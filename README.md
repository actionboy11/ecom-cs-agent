# 电商售后客服 Agent（E-commerce After-Sales Support Agent）

[![CI](https://github.com/actionboy11/ecom-cs-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/actionboy11/ecom-cs-agent/actions/workflows/ci.yml)

**一个能上生产的售后客服 Agent 参考实现**：LangGraph 编排 + MCP 工具化 + 资源级鉴权 + 三层可复现评测。

> 不是又一个 RAG 客服 demo。这个项目回答一个具体问题：**当 AI 客服出错时，系统怎么办？**

**仓库**：https://github.com/actionboy11/ecom-cs-agent ｜ [规格书](docs/SPEC.md) ｜ [项目总报告](docs/PROJECT-REPORT.md) ｜ [词汇表](GLOSSARY.md) ｜ [每日开发记录](docs/daily/) ｜ [决策记录](docs/adr/)

---

## 为什么做这个项目

调研了 12 个 GitHub 同类项目（见 [对标笔记](docs/daily/2026-11-02.md)）后发现三个空白：

| 空白 | 本项目怎么做 |
|---|---|
| 几乎都没做**资源级鉴权**（有项目在 README 自认 `user_id` 未认证） | JWT + 订单归属校验 + 越权统一 404 + 审计 |
| 很少有**失败路径**的演示（只演示成功对话） | 转人工中断/恢复、工具降级、写操作审批、拒答边界 |
| **评测**要么缺失、要么自建自测 | 公开 600 条基准 + 自建 60 条（含 holdout）+ 真实对话质量评测 |

## 架构

```
用户浏览器
   │
   ▼
Streamlit（双栏：买家对话 / 坐席审批）
   │
   ▼
Python: FastAPI + LangGraph
  ├─ classify → knowledge(Chroma) / tools / handoff
  ├─ checkpointer(SQLite)：会话续跑
  ├─ interrupt：转人工审批
  └─ Trace(JSONL)
   │ MCP（工具调用，user_id 由服务端注入，模型不可见）
   ▼
Java: Spring Boot 3 + Spring Security(JWT) + MyBatis-Plus
  ├─ 订单 / 物流 / 退款 / 商品 / 审计
  └─ Flyway 迁移 + MySQL
```

## 五个演示场景

1. **查物流**：多轮补槽 → 工具调用 → 轨迹 + 超时提示
2. **申请退款**：校验政策 → 创建 PENDING → 坐席审批 → 状态回写
3. **投诉**：情绪触发 → 先落盘再中断 → 恢复
4. **商品咨询**：参数/尺码/库存 → 商品工具
5. **越权尝试**：查他人订单 → 404 + 审计 DENIED

## 快速开始

```bash
cp .env.example .env        # 填 DEEPSEEK_API_KEY / JWT_SECRET / INTERNAL_AUDIT_TOKEN
docker compose up -d         # MySQL + Java + Python Agent + 工作台
# 浏览器打开 http://localhost:8501
```

演示流程见 [docs/DEMO.md](docs/DEMO.md)；镜像命名、推送与回滚见 [docs/DEPLOY.md](docs/DEPLOY.md)；开发排期见 [SPEC 第 12 节](docs/SPEC.md)。

## 录屏清单（5 分钟）

1. 终端 `docker compose ps`：mysql / java-service / python-agent / workbench 四个 healthy
2. 买家登录 + S1 查物流
3. S2 退款申请（展示售后请求编号与 PENDING）
4. S3 投诉 → 「已转接人工坐席」
5. S4 商品咨询（建过索引时放大 `[P0x]`）
6. S5 越权 → 统一「没有找到对应的记录」
7. 坐席侧审计面板 + 结尾一页评测数字

详细输入、预期与兜底见 [docs/DEMO.md](docs/DEMO.md)。

## 工作台（Streamlit）

左右两栏：左栏买家对话（走 Agent），右栏坐席审批与审计（走 Java REST）。`docker compose up -d` 已包含该服务（<http://localhost:8501>）。

不用容器时：

```bash
cd python-agent
JAVA_BASE=http://localhost:8080 AGENT_BASE=http://localhost:8000 \
  uv run streamlit run ui/app.py
```

> 本地用 uvicorn 跑 Agent（端口 8010）时，把 `AGENT_BASE` 改成 `http://localhost:8010`。

- 演示账号：`buyer_a` / `cs_agent`，密码均为 `demo123`（种子数据）
- 非坐席账号登录时，审批区显示「不可用」而不是只隐藏按钮
- 人工转接后买家只能等待；坐席在右栏「恢复转接会话」里审批并恢复（`/resume` 仅坐席可用）
- UI 只做编排：接口逻辑在 `ui/api_client.py`，纯逻辑在 `ui/logic.py`，都有单测；页面用 `streamlit.testing` 做加载测试


## 评测（持续更新）

| 层 | 数据 | 指标 | 结果 |
|---|---|---|---|
| 标准 | 本地等效用例 600 条（抽样 100；公开集未分发，**无许可**，适配器见下） | 回复符合率（等效用例代理，非 oracle） | 76.0%（100 条抽样） |
| 业务 | 自建 60 条（全量；`--split/--holdout` 可切分） | 意图/工具/回复 | 意图 100% / 工具 98.3% / 回复 80.0% |
| 业务 | 政策类 8 条（标注 `expect_citation`） | **引用命中率（回答正文）** | **100%（8/8）** |
| 业务 | 政策类 8 条 | 检索命中率（主依据） | 100%（8/8） |
| 安全 | 越权 4 条 | 拦截率 + 新增 DENIED 审计 | 100%（4/4；覆盖 3 个目标资源） |
| 安全 | 拒答 9 条（四类） | 回复符合率 | 100%（9/9） |

复现（需要 Java 业务系统在线，否则工具类用例会计为失败）：

```bash
uv run python -m eval.run_all --standard-limit 100 --out-dir docs/eval   # 三层（含越权）一次跑完
uv run python -m eval.security_check                 # 只跑 4 条越权 + 审计校验
uv run python -m eval.run_eval --cases eval/business_cases.jsonl
uv run python -m eval.public_bench --source <公开集.jsonl>       # 公开集适配（不内置数据）
uv run python -m eval.gen_standard_cases             # 重新生成 600 条等效用例
```

报告写到 `eval/reports/`（不提交）；基线由脚本生成并提交到 `docs/eval/`（`three-layers-*.md`），报告内标注数据来源、链路（LLM/兜底）与许可状态。

**数据说明**：公开 600 条售后基准（csnewerst）未随仓库分发、离线无法下载，`eval/standard_cases.jsonl` 是确定性生成的**等效用例**，不是公开集；报告与表格均标注来源。

## 目录

```
java-service/    Spring Boot 业务系统 + 鉴权 + MCP Server
python-agent/    LangGraph Agent + 评测 + Streamlit
data/policies/   售后政策库（12 条）
docs/            SPEC / 每日记录 / 简历
```

## 设计取舍

- **业务数据用 MySQL，Agent 状态用 SQLite**：前者要事务和 join，后者是高频小写入。
- **越权返回 404 而不是 403**：403 会泄露资源是否存在，可被用来枚举。
- **关键词规则只做降级兜底，不计入质量指标**：规则一旦参与评测，就会变成为评测集调参。

## 知识检索（Chroma）

12 条售后政策放在 `data/policies/policies.md`，建立索引：

```bash
ollama pull bge-m3                          # 首次
uv run python -m app.knowledge.ingest --rebuild   # 重建索引（首次或政策更新后）
```

- 索引已存在时必须显式 `--rebuild`；重建前会先算好向量，嵌入失败不会清空现有索引

- 向量库为本地持久化 Chroma（`data/chroma`），embedding 用 Ollama `bge-m3`（1024 维）
- 检索结果带 `[P0x]` 引用，回答里保留编号便于核对
- Chroma 或 Ollama 不可用时自动退化为关键词检索，对话不中断
- Windows 若报 `unable to open database file (code 14)`：系统临时目录不可写，程序已自动把 `TMP/TEMP` 指向仓库内 `.tmp`

## 会话数据保留（TTL）

Agent 会话与轨迹默认保留 **30 天**（`SESSION_TTL_DAYS`），业务审计不受影响（审计在 MySQL，按 365 天保留）。

- 服务启动时自动清理一次；
- 手动执行（先预览，再真删）：

```bash
uv run python -m app.maintenance.cleanup --dry-run   # 只统计
uv run python -m app.maintenance.cleanup             # 实际删除
```

- 每日定时：Linux 用 cron，Windows 用任务计划程序：

```cron
30 3 * * * cd /path/to/python-agent && uv run python -m app.maintenance.cleanup >> retention.log 2>&1
```

Windows（任务计划程序 → 创建基本任务 → 每天 03:30）：

```powershell
pwsh -NoProfile -Command "cd C:\path\to\python-agent; uv run python -m app.maintenance.cleanup"
```

退出码：`0` 成功，`2` 参数/状态库不存在，`3` 执行异常，`4` 文件删除失败（便于 cron 告警）。

## 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| Spring Boot 启动报 `Communications link failure` | MySQL 容器没起来；宿主机 3306 被本机 MySQL、3307 常被其他项目容器占用 | 本项目容器映射到 **3308**（`3308→3306`）；先 `docker compose up -d mysql`，等 healthy |
| 测试连到别的库 / `Access denied for user 'xxx'` | 系统里其他项目设置的全局 `SPRING_DATASOURCE_URL` 优先级高于 yml | 已在 surefire 显式覆盖；本地启动应用时用 `--spring.datasource.url=...` 或清掉该变量 |
| 启动 uvicorn 报 `[WinError 10013]` | 端口被占用或被 Windows 动态保留 | 换端口 `--port 8010`；或管理员执行 `net stop winnat` / `net start winnat` |
| Agent 返回「业务系统错误 502」，但 `curl localhost:8080` 正常 | 系统代理把 localhost 也代理走了 | 已通过 `trust_env=False` 规避 |
| `uv` 找不到 | PATH 未刷新 | 重开终端 |

## Roadmap

- [x] W0 脚手架：LangGraph 图 + Java 接口 + 10 条评测
- [x] W1 MySQL + JWT + 资源归属校验（越权 404、审计落库、21+ 用例）
- [ ] W2 Chroma 检索 + MCP 工具化
- [ ] W3 三层评测 + 拒答边界
- [ ] W4 Streamlit 双栏 + Docker 一键启动
- [ ] W5 subgraph 多 Agent + 多模型成本对比
- [ ] W6 技术文章 + 面试题库

---

## English

An after-sales customer-support agent that focuses on what demos usually skip: **failure paths and authorization**.

- **Graph**: LangGraph state machine with checkpointing, human-in-the-loop interrupts, and subgraphs.
- **Tools**: MCP-exposed tools backed by a real Spring Boot service; `user_id` is injected server-side and never exposed to the model.
- **Security**: JWT auth, per-resource ownership checks, 404-on-unauthorized (no existence leak), audit trail.
- **Evaluation**: public 600-case benchmark + 60 hand-written cases with a hold-out split + quality review on real conversations.

See [SPEC.md](docs/SPEC.md) for the full specification.

## License

MIT
