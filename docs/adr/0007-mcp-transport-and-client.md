# ADR-0007：MCP 传输与客户端实现

- 状态：已接受
- 日期：2026-11-10
- 相关：SPEC §7.1 / §7.2、切片 5（#21 / #22 / #23）

## 背景

SPEC 要求 Agent 通过 MCP 操作业务系统，工具清单见 §7.1。最初的计划是用 Spring AI 的 MCP Server（Streamable HTTP），Python 侧用官方 `mcp` SDK。

实际实现时遇到两个硬约束：

1. **Spring AI 1.0.3–1.1.8 未向 `@Tool` 方法暴露请求级 transport context**。SSE 传输下，工具在另一个线程执行，Filter 写入的 `ThreadLocal` 已清空，工具拿不到登录身份。
2. **官方 Python SDK 的 `streamable_http_client` 需要会话协商**（`Mcp-Session-Id`、SSE 流），而我们的 `/mcp` 是单次 JSON-RPC 请求-响应，二者无法直接对接。

## 决策

1. **传输**：Java 暴露 `POST /mcp`，请求体是标准 JSON-RPC 2.0（`initialize` / `tools/list` / `tools/call` / `ping`），响应是普通 JSON。
2. **身份**：从 `Authorization: Bearer <jwt>` 由 Spring Security 解析，控制器在同一线程内注入 `McpAuthContext`；工具参数里没有 user_id。
3. **客户端**：Python 侧手写轻量 JSON-RPC 客户端（`app/tools/mcp_client.py`），不引入官方 `mcp` SDK。
4. **附加传输**：保留 MCP stdio 服务端（进程级身份），用于「一个用户一个进程」的场景；HTTP 是默认路径。

## 后果

- **正面**：实现小、可单测、身份不可伪造；不依赖 Spring AI 的版本演进。
- **负面**：
  - 不是完整的 Streamable HTTP MCP（无会话、无 SSE、无 `notifications/*` 之外的服务端推送），第三方 MCP 客户端接入需要适配；
  - 与「备注要求官方 SDK」存在偏差，已在本 ADR 与 #23 票面记录；
  - 若未来切换到标准 MCP Server，需要重写 Python 客户端的传输层（协议方法名与参数可保持不变）。

## 何时重新评估

- Spring AI 提供可用的 transport context 注入；
- 或需要让第三方 MCP 客户端（如 Claude Desktop）直连业务系统时，改用官方 SDK + Streamable HTTP。
