package com.example.csagent.mcp;

import com.example.csagent.domain.Logistics;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.LogisticsQueryService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/** MCP 工具：物流查询（SPEC §7.1 `query_logistics`）。 */
@Component
public class LogisticsMcpTools implements McpTool {

    public static final String NAME = "query_logistics";

    private final LogisticsQueryService logisticsQueryService;
    private final ObjectMapper objectMapper;

    public LogisticsMcpTools(LogisticsQueryService logisticsQueryService, ObjectMapper objectMapper) {
        this.logisticsQueryService = logisticsQueryService;
        this.objectMapper = objectMapper;
    }

    public String queryLogistics(String orderNo) throws Exception {
        if (orderNo == null || orderNo.isBlank()) {
            throw new MissingSlotException("MISSING_SLOT: 缺少订单号 order_no");
        }
        AuthenticatedUser user = McpAuthContext.require();
        Logistics logistics = logisticsQueryService.findByOrderNo(orderNo, user, "/mcp");
        return objectMapper.writeValueAsString(logistics);
    }

    @Override
    public List<McpProtocol.ToolSpec> specs() {
        return List.of(new McpProtocol.ToolSpec(
                NAME,
                "查询物流轨迹；只能查自己的订单",
                Map.of(
                        "type", "object",
                        "properties", Map.of(
                                "order_no", Map.of("type", "string", "description", "订单号，例如 CS2024001")),
                        "required", List.of("order_no"),
                        "additionalProperties", false),
                args -> queryLogistics((String) args.get("order_no"))));
    }
}
