# 业务数据放 MySQL，Agent 会话状态放 SQLite

## Status

accepted

## Context

项目同时存在两类数据：用户/订单/物流/退款/审计是关系型、需要事务与 join；LangGraph 的 checkpoint 是高频小写入的键值状态，按 `thread_id` 读写。

## Decision

业务数据全部落 **MySQL**（Flyway 迁移 + MyBatis-Plus）；Agent 运行状态落 **SQLite**（`langgraph-checkpoint-sqlite` 官方实现），同库再存一张 `thread_owner` 表做会话归属。

## Considered Options

- **全部 MySQL**：一致性好、运维单一，但 Python 侧要引入连接池，checkpoint 每次节点结束都写一次，会成为热点；且 Agent 状态与业务数据的生命周期完全不同（前者可丢、后者不可丢）。
- **全部 SQLite**：零依赖，但业务查询需要事务与索引，审计与退款状态需要可靠性，不适合。

## Consequences

- 两套存储 → 两套备份与迁移策略；演示时需说明各自职责。
- 清空 SQLite 会丢失会话，但业务数据不受影响——这是有意为之的隔离。
- 生产环境若把 checkpoint 换成 Postgres/Redis，业务层无需改动。
