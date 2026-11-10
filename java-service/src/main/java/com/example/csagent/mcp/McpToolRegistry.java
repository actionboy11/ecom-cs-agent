package com.example.csagent.mcp;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/** 工具清单：由各工具自己声明，注册中心只做汇总。 */
@Component
public class McpToolRegistry {

    private final List<McpTool> tools;
    private final ObjectMapper objectMapper;

    public McpToolRegistry(List<McpTool> tools, ObjectMapper objectMapper) {
        this.tools = tools;
        this.objectMapper = objectMapper;
    }

    public List<McpProtocol.ToolSpec> tools() {
        List<McpProtocol.ToolSpec> specs = new ArrayList<>();
        tools.forEach(tool -> specs.addAll(tool.specs()));
        return specs;
    }

    public McpProtocol protocol() {
        return new McpProtocol(tools(), objectMapper);
    }
}
