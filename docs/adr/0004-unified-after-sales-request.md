# 售后请求统一建模，而不是分开建退款/退货/换货三张表

## Status

accepted

## Context

买家的售后诉求有三类：退款（不退货）、退货（寄回后退款）、换货（寄回后换规格）。三者共享同一套流程：校验归属 → 校验政策 → 创建待审请求 → 坐席审批 → 更新状态；差异只在「是否需要寄回」与「财务动作」。

## Decision

统一建一张 `after_sales_requests` 表，用 `type ENUM('REFUND','RETURN','EXCHANGE')` 区分；对外一个接口 `POST /api/after-sales`，一个 MCP 工具 `create_after_sales_request`。

## Considered Options

- **三张表 / 三个接口**：类型差异显式，但审批、审计、状态机要复制三份，坐席面板也要三个列表。
- **统一表 + type 字段**：状态机与审批复用，代价是某些字段对某些类型无意义（如换货没有金额）。

## Consequences

- 换货与退货的「寄回」环节需要额外的物流单，v1 只记录状态，不做寄回单。
- 报表需要按 `type` 分组，否则口径会混。
- 该命名与公开评测集（csnewerst 600 条）的 oracle 工具一致，适配层少一层映射。
