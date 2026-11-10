package com.example.csagent.mcp;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.List;

/** 工具清单：HTTP 端点与 stdio 服务端共用同一份注册。 */
@Component
public class McpToolRegistry {

    private final OrderMcpTools orderTools;
    private final LogisticsMcpTools logisticsTools;
    private final AfterSalesMcpTools afterSalesTools;
    private final ObjectMapper objectMapper;

    public McpToolRegistry(OrderMcpTools orderTools, LogisticsMcpTools logisticsTools,
                           AfterSalesMcpTools afterSalesTools, ObjectMapper objectMapper) {
        this.orderTools = orderTools;
        this.logisticsTools = logisticsTools;
        this.afterSalesTools = afterSalesTools;
        this.objectMapper = objectMapper;
    }

    public List<McpProtocol.ToolSpec> tools() {
        return List.of(
                new McpProtocol.ToolSpec(
                        OrderMcpTools.NAME,
                        "查询订单详情；只能查当前登录用户自己的订单，他人订单返回不存在",
                        OrderMcpTools.schema(),
                        args -> orderTools.getOrder((String) args.get("orderNo"))),
                new McpProtocol.ToolSpec(
                        LogisticsMcpTools.NAME,
                        "查询物流轨迹；只能查自己的订单",
                        LogisticsMcpTools.schema(),
                        args -> logisticsTools.getLogistics((String) args.get("orderNo"))),
                new McpProtocol.ToolSpec(
                        AfterSalesMcpTools.APPLY,
                        "发起售后申请（退款/退货/换货）；仅买家可用",
                        AfterSalesMcpTools.applySchema(),
                        args -> afterSalesTools.applyAfterSales(
                                (String) args.get("orderNo"),
                                (String) args.get("type"),
                                (String) args.get("reason"))),
                new McpProtocol.ToolSpec(
                        AfterSalesMcpTools.LIST,
                        "查询售后列表；买家仅自己，坐席可看全部，可按状态过滤",
                        AfterSalesMcpTools.listSchema(),
                        args -> afterSalesTools.listAfterSales((String) args.get("status"))));
    }

    public McpProtocol protocol() {
        return new McpProtocol(tools(), objectMapper);
    }
}
