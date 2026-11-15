package com.example.csagent.mcp;

import com.example.csagent.domain.Order;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.OrderQueryService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/** MCP 工具：订单查询（SPEC §7.1 `query_order`）。 */
@Component
public class OrderMcpTools implements McpTool {

    public static final String NAME = "query_order";
    public static final String LIST_NAME = "list_my_orders";

    private final OrderQueryService orderQueryService;
    private final ObjectMapper objectMapper;

    public OrderMcpTools(OrderQueryService orderQueryService, ObjectMapper objectMapper) {
        this.orderQueryService = orderQueryService;
        this.objectMapper = objectMapper;
    }

    public String queryOrder(String orderNo) throws Exception {
        if (orderNo == null || orderNo.isBlank()) {
            throw new MissingSlotException("MISSING_SLOT: 缺少订单号 order_no");
        }
        AuthenticatedUser user = McpAuthContext.require();
        Order order = orderQueryService.findByOrderNo(orderNo, user, "/mcp");
        return objectMapper.writeValueAsString(order);
    }

    public String listMyOrders() throws Exception {
        AuthenticatedUser user = McpAuthContext.require();
        List<Order> orders = orderQueryService.listFor(user, "/mcp");
        return objectMapper.writeValueAsString(orders);
    }

    @Override
    public List<McpProtocol.ToolSpec> specs() {
        return List.of(
                new McpProtocol.ToolSpec(
                        NAME,
                        "查询订单详情；只能查当前登录用户自己的订单，他人订单返回不存在",
                        Map.of(
                                "type", "object",
                                "properties", Map.of(
                                        "order_no", Map.of("type", "string", "description", "订单号，例如 CS2024001")),
                                "required", List.of("order_no"),
                                "additionalProperties", false),
                        args -> queryOrder((String) args.get("order_no"))),
                new McpProtocol.ToolSpec(
                        LIST_NAME,
                        "列出当前登录用户的全部订单（订单号、商品、状态、下单时间）；用于用户只描述商品时的候选匹配",
                        Map.of("type", "object", "properties", Map.of(), "additionalProperties", false),
                        args -> listMyOrders()));
    }
}
