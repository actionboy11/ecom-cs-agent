package com.example.csagent.mcp;

import com.example.csagent.domain.OrderEntity;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.AuditEvent;
import com.example.csagent.service.OrderAccessGuard;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * MCP 工具实现：订单查询。
 *
 * <p>身份取自 {@link McpAuthContext}（stdio 进程启动时由客户端注入 JWT），
 * 工具参数里没有 user_id；越权与不存在同为 404（ADR-0001）。
 */
@Component
public class OrderMcpTools {

    public static final String NAME = "get_order";

    private final OrderAccessGuard orderAccessGuard;
    private final ObjectMapper objectMapper;

    public OrderMcpTools(OrderAccessGuard orderAccessGuard, ObjectMapper objectMapper) {
        this.orderAccessGuard = orderAccessGuard;
        this.objectMapper = objectMapper;
    }

    public String getOrder(String orderNo) throws JsonProcessingException {
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

    public static Map<String, Object> schema() {
        return Map.of(
                "type", "object",
                "properties", Map.of(
                        "orderNo", Map.of("type", "string", "description", "订单号，例如 CS2024001")),
                "required", java.util.List.of("orderNo"),
                "additionalProperties", false);
    }
}
