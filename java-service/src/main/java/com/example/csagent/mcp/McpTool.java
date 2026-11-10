package com.example.csagent.mcp;

import java.util.List;

/** 一个 MCP 工具提供者：自己声明工具清单，新增工具不再改注册中心。 */
public interface McpTool {

    List<McpProtocol.ToolSpec> specs();
}
