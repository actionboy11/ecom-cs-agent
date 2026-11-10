package com.example.csagent.mcp;

import com.example.csagent.domain.AfterSalesRequest;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.AfterSalesService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/** MCP 工具：售后申请（SPEC §7.1 `create_after_sales_request`，另加只读列表）。 */
@Component
public class AfterSalesMcpTools implements McpTool {

    public static final String CREATE = "create_after_sales_request";
    public static final String LIST = "list_after_sales";
    private static final int MAX_REASON_LENGTH = 200;

    private final AfterSalesService afterSalesService;
    private final ObjectMapper objectMapper;

    public AfterSalesMcpTools(AfterSalesService afterSalesService, ObjectMapper objectMapper) {
        this.afterSalesService = afterSalesService;
        this.objectMapper = objectMapper;
    }

    public String createAfterSalesRequest(String orderNo, String type, String reason) throws Exception {
        AuthenticatedUser user = McpAuthContext.require();
        if (orderNo == null || orderNo.isBlank()) {
            throw new MissingSlotException("MISSING_SLOT: 缺少订单号 order_no");
        }
        if (reason == null || reason.isBlank()) {
            throw new MissingSlotException("MISSING_SLOT: 缺少售后原因 reason");
        }
        if (reason.length() > MAX_REASON_LENGTH) {
            throw new com.example.csagent.service.InvalidInputException(
                    "售后原因超过 " + MAX_REASON_LENGTH + " 字");
        }
        // 类型校验与「仅买家」都在 AfterSalesService 里，REST 与 MCP 共用同一份规则
        AfterSalesRequest created = afterSalesService.create(orderNo, type, reason, user, "/mcp");
        return objectMapper.writeValueAsString(created);
    }

    public String listAfterSales(String status) throws Exception {
        AuthenticatedUser user = McpAuthContext.require();
        List<AfterSalesRequest> rows = afterSalesService.listFor(user, status, "/mcp");
        return objectMapper.writeValueAsString(rows);
    }

    @Override
    public List<McpProtocol.ToolSpec> specs() {
        return List.of(
                new McpProtocol.ToolSpec(
                        CREATE,
                        "发起售后申请（退款/退货/换货）；仅买家可用",
                        Map.of(
                                "type", "object",
                                "properties", Map.of(
                                        "order_no", Map.of("type", "string", "description", "订单号"),
                                        "type", Map.of("type", "string", "enum",
                                                List.of("REFUND", "RETURN", "EXCHANGE")),
                                        "reason", Map.of("type", "string", "maxLength", 200,
                                                "description", "售后原因")),
                                "required", List.of("order_no", "type", "reason"),
                                "additionalProperties", false),
                        args -> createAfterSalesRequest(
                                (String) args.get("order_no"),
                                (String) args.get("type"),
                                (String) args.get("reason"))),
                new McpProtocol.ToolSpec(
                        LIST,
                        "查询售后列表；买家仅自己，坐席可看全部，可按状态过滤",
                        Map.of(
                                "type", "object",
                                "properties", Map.of(
                                        "status", Map.of("type", "string", "enum",
                                                List.of("PENDING", "APPROVED", "REJECTED"))),
                                "additionalProperties", false),
                        args -> listAfterSales((String) args.get("status"))));
    }
}
