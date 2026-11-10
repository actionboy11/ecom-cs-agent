package com.example.csagent.mcp;

import com.example.csagent.domain.Logistics;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.LogisticsQueryService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/** MCP 工具：物流查询（复用 REST 的鉴权与审计）。 */
@Component
public class LogisticsMcpTools {

    public static final String NAME = "get_logistics";

    private final LogisticsQueryService logisticsQueryService;
    private final ObjectMapper objectMapper;

    public LogisticsMcpTools(LogisticsQueryService logisticsQueryService, ObjectMapper objectMapper) {
        this.logisticsQueryService = logisticsQueryService;
        this.objectMapper = objectMapper;
    }

    public String getLogistics(String orderNo) throws Exception {
        if (orderNo == null || orderNo.isBlank()) {
            throw new MissingSlotException("MISSING_SLOT: 缺少订单号 orderNo");
        }
        AuthenticatedUser user = McpAuthContext.require();
        Logistics logistics = logisticsQueryService.findByOrderNo(orderNo, user, "/mcp");
        return objectMapper.writeValueAsString(Map.of(
                "orderNo", logistics.orderNo(),
                "carrier", logistics.carrier(),
                "trackingNo", logistics.trackingNo(),
                "status", logistics.status(),
                "traces", logistics.traces()));
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
