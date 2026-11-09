package com.example.csagent.mcp;

import com.example.csagent.api.NotFoundException;
import com.example.csagent.domain.Order;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.OrderQueryService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * MCP 工具：订单查询。
 *
 * <p>身份取自 {@link McpAuthContext}（HTTP 由登录上下文注入，stdio 由启动参数注入），
 * 工具参数只有订单号；查询复用 {@link OrderQueryService}，与 REST 共享同一份鉴权与审计。
 */
@Component
public class OrderMcpTools {

    public static final String NAME = "get_order";

    private final OrderQueryService orderQueryService;
    private final ObjectMapper objectMapper;

    public OrderMcpTools(OrderQueryService orderQueryService, ObjectMapper objectMapper) {
        this.orderQueryService = orderQueryService;
        this.objectMapper = objectMapper;
    }

    public String getOrder(String orderNo) throws Exception {
        if (orderNo == null || orderNo.isBlank()) {
            throw new MissingSlotException("MISSING_SLOT: 缺少订单号 orderNo");
        }
        AuthenticatedUser user = McpAuthContext.require();
        Order order = orderQueryService.findByOrderNo(orderNo, user, "/mcp");

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("orderNo", order.orderNo());
        result.put("item", order.item());
        result.put("amount", order.amount());
        result.put("status", order.status());
        result.put("createdAt", String.valueOf(order.createdAt()));
        return objectMapper.writeValueAsString(result);
    }

    public static Map<String, Object> schema() {
        return Map.of(
                "type", "object",
                "properties", Map.of(
                        "orderNo", Map.of("type", "string", "description", "订单号，例如 CS2024001")),
                "required", List.of("orderNo"),
                "additionalProperties", false);
    }
}
