# 5 分钟演示流程单

> 用途：录屏或面试现场。按顺序执行，每步只说一句话；翻车时看「兜底」。
> 场景编号与 [SPEC §3](SPEC.md) 一致（S1 物流 / S2 退款 / S3 投诉 / S4 商品 / S5 越权），不重新编号。

## 前置

```bash
cp .env.example .env      # 填 DEEPSEEK_API_KEY / JWT_SECRET / INTERNAL_AUDIT_TOKEN
docker compose up -d      # 等 compose ps 里 mysql/java/python/workbench 都 healthy
```

- 语义检索（可选，否则关键词兜底）：宿主机跑 Ollama，然后
  `docker compose exec python-agent python -m app.knowledge.ingest --rebuild`
- 演示账号：`buyer_a` / `cs_agent`，密码 `demo123`

## 时间轴

| 时间 | 场景 | 栏位 | 输入 | 预期 |
|---|---|---|---|---|
| 0:00–0:30 | 登录 | 侧边栏 | `buyer_a` / `demo123` | 双栏出现；右侧提示「非坐席不可用」 |
| 0:30–1:20 | S1 查物流 | 买家 | `CS2024001 到哪了` | 物流状态 + 最近轨迹（该单为「已签收」） |
| 1:20–2:10 | S2 退款 | 买家 | `CS2024002 耳机有杂音，我要退款` | 生成售后请求编号，状态 PENDING |
| 2:10–3:00 | S3 投诉 | 买家 | `你们客服态度太差了，我要投诉` | 回复「已转接人工坐席」 |
| 3:00–3:50 | S4 商品 | 买家 | `降噪耳机续航多久` | 商品参数；建过索引时附带 `[P0x]` 引用 |
| 3:50–4:40 | S5 越权 | 买家 | `查一下 CS2024005 的物流` | 统一「没有找到对应的记录」，不暴露是否存在 |
| 4:40–5:00 | 审计 | `cs_agent` | 右侧展开「最近审计」 | 看到 LOGIN、QUERY_LOGISTICS/DENIED 等记录 |

若时间富余：用 `cs_agent` 在右侧审批 S2 的 PENDING 请求（通过/驳回 + 备注）。

## 每步口播

- **登录**：身份来自 Java JWT；买家与坐席权限不同，UI 只做编排。
- **S1**：走 MCP 工具，模型只能传订单号，用户身份由服务端注入。
- **S2**：售后统一建模（退款/退货/换货一张表），状态机 PENDING → 审批。
- **S3**：投诉走人工转接分支；回复先落盘再挂起，恢复后不丢上下文。
- **S4**：商品参数来自业务系统；政策部分走 Chroma 检索（未建索引则关键词兜底）。
- **S5**：越权统一 404 文案 + DENIED 审计，避免资源枚举。
- **审计**：登录与越权都写 MySQL，坐席可查。

## 兜底

| 现象 | 处理 |
|---|---|
| 回答像模板 | 正常：模型超时降级模板，说明「兜底链路，评测里单独统计」 |
| 政策回答没有 `[P0x]` | 说明未建索引或相似度低于 0.35，展示拒答而不是硬编 |
| 审批列表为空 | 先做 S2 生成 PENDING；仍为空则 `docker compose logs java-service` |
| 右侧报「无法连接」 | `docker compose ps` 看依赖是否 healthy；`docker compose logs python-agent` |
| 越权演示返回 401 | JWT 2 小时过期，重新登录 |

## 录屏清单

1. 终端：`docker compose ps` 四个服务 healthy
2. 买家登录 + S1 物流
3. S2 退款（展示售后请求编号与 PENDING）
4. S3 投诉 → 「已转接人工坐席」
5. S4 商品（有索引时放大 `[P0x]`）
6. S5 越权 + 坐席侧审计面板
7. 结尾：`docs/eval/` 三层评测与拒答基线

## 演示后自检

```bash
curl -s localhost:8080/api/health
curl -s localhost:8000/api/v1/health
curl -s localhost:8501/_stcore/health
```
