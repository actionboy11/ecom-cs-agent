package com.example.csagent.mcp;

import com.example.csagent.domain.OrderEntity;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.AuditEvent;
import com.example.csagent.service.OrderAccessGuard;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * MCP 工具：订单查询。
 *
 * <p>身份取自 {@link McpAuthContext}（请求头 JWT），工具参数里没有 user_id，
 * 模型就算想越权也没有可传的字段；越权与不存在同为 404（ADR-0001）。
 */
@Component
public class OrderMcpTools {

    private final OrderAccessGuard orderAccessGuard;
    private final ObjectMapper objectMapper;

    public OrderMcpTools(OrderAccessGuard orderAccessGuard, ObjectMapper objectMapper) {
        this.orderAccessGuard = orderAccessGuard;
        this.objectMapper = objectMapper;
    }

    @Tool(name = "get_order", description = "查询订单详情；只能查当前登录用户自己的订单，他人订单返回不存在")
    public String getOrder(@ToolParam(description = "订单号，例如 CS2024001") String orderNo)
            throws JsonProcessingException {
        AuthenticatedUser user = McpAuthContext.require();
        OrderEntity order = orderAccessGuard.requireVisible(
                orderNo, user, AuditEvent.ACTION_QUERY_ORDER, AuditEvent.TYPE_ORDER, "/mcp");

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("orderNo", order.getOrderNo());
        result.put("item", order.getItemName());
        result.put("amount", order.getAmount());
        result.put("status", order.getStatus());
        result.put("createdAt", String.valueOf(order.getCreatedAt()));
        return objectMapper.writeValueAsString(result);
    }
}
