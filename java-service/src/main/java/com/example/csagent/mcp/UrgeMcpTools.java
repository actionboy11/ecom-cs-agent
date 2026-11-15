package com.example.csagent.mcp;

import com.example.csagent.domain.AfterSalesRequest;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.AfterSalesService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/** MCP 工具：催件（落一条 URGE 售后请求，可被坐席审批/审计）。 */
@Component
public class UrgeMcpTools implements McpTool {

    public static final String NAME = "urge_logistics";

    private final AfterSalesService afterSalesService;
    private final ObjectMapper objectMapper;

    public UrgeMcpTools(AfterSalesService afterSalesService, ObjectMapper objectMapper) {
        this.afterSalesService = afterSalesService;
        this.objectMapper = objectMapper;
    }

    public String urge(String orderNo, String reason) throws Exception {
        AuthenticatedUser user = McpAuthContext.require();
        if (orderNo == null || orderNo.isBlank()) {
            throw new MissingSlotException("MISSING_SLOT: 缺少订单号 order_no");
        }
        String text = (reason == null || reason.isBlank()) ? "用户申请催件" : reason;
        AfterSalesRequest created =
                afterSalesService.create(orderNo, "URGE", text, user, "/mcp");
        return objectMapper.writeValueAsString(created);
    }

    @Override
    public List<McpProtocol.ToolSpec> specs() {
        return List.of(new McpProtocol.ToolSpec(
                NAME,
                "对物流停滞的订单发起催件；仅买家可用，会生成一条 URGE 售后请求",
                Map.of(
                        "type", "object",
                        "properties", Map.of(
                                "order_no", Map.of("type", "string", "description", "订单号"),
                                "reason", Map.of("type", "string", "maxLength", 200,
                                        "description", "催件原因，可省略")),
                        "required", List.of("order_no"),
                        "additionalProperties", false),
                args -> urge((String) args.get("order_no"), (String) args.get("reason"))));
    }
}
