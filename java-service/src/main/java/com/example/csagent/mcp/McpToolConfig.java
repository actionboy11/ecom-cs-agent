package com.example.csagent.mcp;

import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** 把 @Tool 方法注册成 MCP 工具。 */
@Configuration
public class McpToolConfig {

    @Bean
    public ToolCallbackProvider businessToolCallbacks(OrderMcpTools orderMcpTools) {
        return MethodToolCallbackProvider.builder()
                .toolObjects(orderMcpTools)
                .build();
    }
}
