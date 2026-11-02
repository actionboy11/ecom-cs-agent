# 电商售后客服 Agent（E-commerce After-Sales Support Agent）

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
cp .env.example .env        # 填 DEEPSEEK_API_KEY
docker compose up -d         # MySQL + Java + Python + UI
open http://localhost:8501   # Streamlit
```

本地开发见 [SPEC 第 12 节](docs/SPEC.md)。

## 评测（持续更新）

| 层 | 数据 | 指标 | 结果 |
|---|---|---|---|
| 标准 | 公开 600 条售后基准 | 任务完成率 | _待填_ |
| 业务 | 自建 60 条（48 train / 12 holdout） | 意图/工具/回复 | _待填_ |
| 安全 | 越权 4 条 | 拦截率 | _待填_ |

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

## Roadmap

- [x] W0 脚手架：LangGraph 图 + Java 接口 + 10 条评测
- [ ] W1 MySQL + JWT + 资源归属校验
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
