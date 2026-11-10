package com.example.csagent.mcp;

import com.example.csagent.domain.AfterSalesRequest;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.AfterSalesService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** MCP 工具：售后申请（发起 / 列表）。 */
@Component
public class AfterSalesMcpTools {

    public static final String APPLY = "apply_after_sales";
    public static final String LIST = "list_after_sales";
    private static final Set<String> VALID_TYPES = Set.of("REFUND", "RETURN", "EXCHANGE");

    private final AfterSalesService afterSalesService;
    private final ObjectMapper objectMapper;

    public AfterSalesMcpTools(AfterSalesService afterSalesService, ObjectMapper objectMapper) {
        this.afterSalesService = afterSalesService;
        this.objectMapper = objectMapper;
    }

    public String applyAfterSales(String orderNo, String type, String reason) throws Exception {
        AuthenticatedUser user = McpAuthContext.require();
        if (user.isCustomerServiceAgent()) {
            throw new ForbiddenException("FORBIDDEN: 售后只能由买家发起");
        }
        if (orderNo == null || orderNo.isBlank()) {
            throw new MissingSlotException("MISSING_SLOT: 缺少订单号 orderNo");
        }
        String normalized = type == null ? "" : type.trim().toUpperCase(java.util.Locale.ROOT);
        if (!VALID_TYPES.contains(normalized)) {
            throw new IllegalArgumentException("INVALID_INPUT: 不支持的售后类型 " + type);
        }
        if (reason == null || reason.isBlank()) {
            throw new MissingSlotException("MISSING_SLOT: 缺少售后原因 reason");
        }

        AfterSalesRequest created = afterSalesService.create(orderNo, normalized, reason, user, "/mcp");
        return objectMapper.writeValueAsString(toView(created));
    }

    public String listAfterSales(String status) throws Exception {
        AuthenticatedUser user = McpAuthContext.require();
        List<Map<String, Object>> rows = afterSalesService.listFor(user, status, "/mcp").stream()
                .map(AfterSalesMcpTools::toView)
                .toList();
        return objectMapper.writeValueAsString(rows);
    }

    private static Map<String, Object> toView(AfterSalesRequest request) {
        Map<String, Object> view = new LinkedHashMap<>();
        view.put("requestNo", request.requestNo());
        view.put("orderNo", request.orderNo());
        view.put("type", request.type());
        view.put("status", request.status());
        view.put("reason", request.reason());
        view.put("createdAt", String.valueOf(request.createdAt()));
        return view;
    }

    public static Map<String, Object> applySchema() {
        return Map.of(
                "type", "object",
                "properties", Map.of(
                        "orderNo", Map.of("type", "string", "description", "订单号"),
                        "type", Map.of("type", "string", "enum", List.of("REFUND", "RETURN", "EXCHANGE")),
                        "reason", Map.of("type", "string", "description", "售后原因")),
                "required", List.of("orderNo", "type", "reason"),
                "additionalProperties", false);
    }

    public static Map<String, Object> listSchema() {
        return Map.of(
                "type", "object",
                "properties", Map.of(
                        "status", Map.of("type", "string", "enum", List.of("PENDING", "APPROVED", "REJECTED"))),
                "additionalProperties", false);
    }
}
