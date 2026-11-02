# 电商售后客服 Agent（cs-agent）

> 4 周项目：把一个「能演示、能报数、能讲透」的 Agent 项目做出来，用于投递中厂「AI Agent 应用开发 / 大模型应用开发（客服·电商方向）」岗位。
> 计划与排期见 [PLAN.md](PLAN.md)。

## 它是什么

用户用自然语言描述售后诉求（查订单 / 查物流 / 申请退款 / 问政策 / 投诉），Agent 完成：

1. 意图识别与槽位抽取（订单号、退款原因）
2. 知识检索（售后政策）
3. 工具调用（订单、物流、退款 —— 通过 MCP 调 Java 业务系统）
4. 多轮澄清 + 会话记忆
5. 必要时 `interrupt` 转人工，人工确认后恢复执行
6. 全链路 Trace → 评测集 → 指标报告

## 架构

```
           ┌──────────────────────────────┐
  用户 ───▶ │ FastAPI (python-agent)       │
           │  └ LangGraph 状态机           │
           │     classify → knowledge/tool │
           │        → handoff(interrupt)   │
           │        → respond              │
           │  ├ Checkpointer(会话续跑)      │
           │  ├ Memory(短期/长期)           │
           │  └ Trace(JSONL)               │
           └───────────┬──────────────────┘
                       │ MCP / HTTP
           ┌───────────▼──────────────────┐
           │ Spring Boot (java-service)    │
           │  订单 / 物流 / 退款 / 审计     │
           └───────────┬──────────────────┘
                       │
                  MySQL (W3 接入)
```

**为什么是 Java + Python 双栈**：Agent 内核必须是 Python（生态与岗位要求），业务系统用 Java —— 既复用既有积累，又能真实体现「Agent 与内部系统集成、权限、审计」这类 JD 高频要求。

## 快速开始

```powershell
# 0) 配置环境变量（多模型，可只填 DeepSeek）
Copy-Item .env.example .env

# 1) Java 业务系统（JDK 21 + Maven）
cd java-service
mvn spring-boot:run          # http://localhost:8080/api/health

# 2) Python Agent（新终端）
cd python-agent
uv sync                       # 未装 uv：python -m venv .venv; .\.venv\Scripts\pip install -e .
uv run uvicorn app.main:app --reload --port 8000
# 文档：http://localhost:8000/docs
# 若报 [WinError 10013]（端口被系统保留或占用），换端口：
#   uv run uvicorn app.main:app --reload --port 8010

# 3) 跑评测
uv run python eval/run_eval.py

# 4) 一键启动（可选，需要镜像构建）
docker compose up --build
```

> 无 API Key 也能启动：意图分类和应答都有规则兜底，方便先验证链路，再接真模型。

## 目录

```
python-agent/        Python Agent 服务（FastAPI + LangGraph）
  app/graph/         状态机：state / nodes / builder
  app/llm/           多模型注册与任务路由
  app/tools/         Java 业务系统客户端（W1 用 HTTP，W2 换 MCP）
  app/observability  Trace
  eval/              评测集与评测脚本
java-service/        Spring Boot 业务系统
docs/daily/          每日开发记录
```

## 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| Agent 返回「业务系统错误 502」，但 `curl localhost:8080/api/health` 正常 | 系统代理把 localhost 也代理走了（企业网络 / 本机代理） | 代码里已用 `trust_env=False` 规避；自己写 HTTP 客户端时同样要注意 |
| 启动 uvicorn 报 `[WinError 10013]` | 端口被占用或被 Windows 动态保留 | 换端口 `--port 8010`；或管理员执行 `net stop winnat` / `net start winnat` |
| 找不到 `uv` 命令 | 安装后 PATH 未刷新 | 关掉终端重开；`winget install --id astral-sh.uv -e` |
| pytest 提示 asyncio fixture loop scope | pytest-asyncio 默认值变更 | 已在 `pyproject.toml` 显式设置 |

## 状态

- [x] W0 骨架：目录、配置、多模型路由、LangGraph 主图、Java 三接口
- [ ] W1 端到端跑通
- [ ] W2 记忆 / 转人工 / 多 Agent
- [ ] W3 评测与优化
- [ ] W4 部署 / 简历 / 投递
