package com.example.csagent.mcp;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.List;

/** 工具清单：HTTP 端点与 stdio 服务端共用同一份注册。 */
@Component
public class McpToolRegistry {

    private final OrderMcpTools orderMcpTools;
    private final ObjectMapper objectMapper;

    public McpToolRegistry(OrderMcpTools orderMcpTools, ObjectMapper objectMapper) {
        this.orderMcpTools = orderMcpTools;
        this.objectMapper = objectMapper;
    }

    public List<McpProtocol.ToolSpec> tools() {
        return List.of(new McpProtocol.ToolSpec(
                OrderMcpTools.NAME,
                "查询订单详情；只能查当前登录用户自己的订单，他人订单返回不存在",
                OrderMcpTools.schema(),
                arguments -> orderMcpTools.getOrder((String) arguments.get("orderNo"))));
    }

    public McpProtocol protocol() {
        return new McpProtocol(tools(), objectMapper);
    }
}
