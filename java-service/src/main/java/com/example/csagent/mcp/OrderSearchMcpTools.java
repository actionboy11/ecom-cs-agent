package com.example.csagent.mcp;

import com.example.csagent.domain.Order;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.OrderQueryService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeParseException;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * MCP 工具：按商品/时间/状态召回当前用户订单，并给出可解释分数。
 * 权限过滤在服务层（只能看自己的单）；Python/ReAct 只消费排序结果。
 */
@Component
public class OrderSearchMcpTools implements McpTool {

    public static final String NAME = "find_my_orders";

    private static final Map<String, List<String>> SYNONYMS = Map.of(
            "耳机", List.of("耳机", "降噪", "蓝牙"),
            "鞋", List.of("鞋", "跑鞋", "运动鞋", "跑步鞋"),
            "行李箱", List.of("行李箱", "登机箱", "箱子"),
            "杯子", List.of("杯", "保温杯", "水杯"),
            "背包", List.of("背包", "双肩包"),
            "充电宝", List.of("充电宝", "移动电源"));

    private final OrderQueryService orderQueryService;
    private final ObjectMapper objectMapper;

    public OrderSearchMcpTools(OrderQueryService orderQueryService, ObjectMapper objectMapper) {
        this.orderQueryService = orderQueryService;
        this.objectMapper = objectMapper;
    }

    public String findMyOrders(Map<String, Object> args) throws Exception {
        AuthenticatedUser user = McpAuthContext.require();
        List<Order> orders = orderQueryService.listFor(user, "/mcp");

        List<String> terms = stringList(args.get("product_terms"));
        LocalDate createdFrom = date(args.get("created_from"));
        LocalDate createdTo = date(args.get("created_to"));
        LocalDate deliveredFrom = date(args.get("delivered_from"));
        LocalDate deliveredTo = date(args.get("delivered_to"));
        String action = stringValue(args.get("action"));
        int limit = intValue(args.get("limit"), 5);

        List<Map<String, Object>> candidates = new ArrayList<>();
        for (Order order : orders) {
            List<String> reasons = new ArrayList<>();
            double product = productScore(order, terms, reasons);
            Double time = timeScore(order, createdFrom, createdTo, deliveredFrom, deliveredTo, reasons);
            Double status = action == null ? null : statusScore(order, action, reasons);
            double recency = recencyScore(order, reasons);

            double weighted = product * 0.45 + recency * 0.10;
            double total = 0.45 + 0.10;
            if (time != null) {
                weighted += time * 0.20;
                total += 0.20;
            }
            if (status != null) {
                weighted += status * 0.15;
                total += 0.15;
            }
            double score = total == 0 ? 0 : weighted / total;

            Map<String, Object> row = new LinkedHashMap<>();
            row.put("orderNo", order.orderNo());
            row.put("item", order.item());
            row.put("amount", order.amount());
            row.put("status", order.status());
            row.put("createdAt", order.createdAt());
            row.put("deliveredAt", order.deliveredAt());
            row.put("score", Math.round(score * 1000.0) / 1000.0);
            row.put("reasons", reasons);
            candidates.add(row);
        }

        candidates.sort(Comparator.comparingDouble(
                (Map<String, Object> row) -> (double) row.get("score")).reversed());
        if (candidates.size() > limit) {
            candidates = new ArrayList<>(candidates.subList(0, limit));
        }
        return objectMapper.writeValueAsString(candidates);
    }

    private static double productScore(Order order, List<String> terms, List<String> reasons) {
        if (terms == null || terms.isEmpty()) {
            return 0;
        }
        String item = order.item() == null ? "" : order.item();
        for (String term : terms) {
            List<String> words = SYNONYMS.getOrDefault(term, List.of(term));
            for (String word : words) {
                if (item.contains(word)) {
                    reasons.add("商品匹配：" + term + " → " + word);
                    return 1.0;
                }
            }
        }
        return 0;
    }

    private static Double timeScore(
            Order order,
            LocalDate createdFrom,
            LocalDate createdTo,
            LocalDate deliveredFrom,
            LocalDate deliveredTo,
            List<String> reasons) {
        boolean hasCreated = createdFrom != null || createdTo != null;
        boolean hasDelivered = deliveredFrom != null || deliveredTo != null;
        if (!hasCreated && !hasDelivered) {
            return null;
        }
        if (hasDelivered) {
            LocalDateTime delivered = order.deliveredAt();
            if (delivered == null) {
                return 0.0;
            }
            LocalDate day = delivered.toLocalDate();
            if (within(day, deliveredFrom, deliveredTo)) {
                reasons.add("签收时间匹配");
                return 1.0;
            }
            return 0.0;
        }
        LocalDate day = order.createdAt();
        if (day != null && within(day, createdFrom, createdTo)) {
            reasons.add("下单时间匹配");
            return 1.0;
        }
        return 0.0;
    }

    private static boolean within(LocalDate day, LocalDate from, LocalDate to) {
        return (from == null || !day.isBefore(from)) && (to == null || !day.isAfter(to));
    }

    private static double statusScore(Order order, String action, List<String> reasons) {
        String status = order.status() == null ? "" : order.status();
        double score;
        switch (action) {
            case "refund", "return", "exchange" -> {
                score = switch (status) {
                    case "已签收" -> 1.0;
                    case "已发货", "运输中" -> 0.4;
                    case "待发货" -> 0.2;
                    default -> 0.3;
                };
            }
            case "logistics", "query" -> {
                score = switch (status) {
                    case "运输中", "已发货", "待发货" -> 1.0;
                    case "已签收" -> 0.3;
                    default -> 0.5;
                };
            }
            default -> score = 0.5;
        }
        if (score >= 0.8) {
            reasons.add("状态匹配：" + status);
        }
        return score;
    }

    private static double recencyScore(Order order, List<String> reasons) {
        if (order.createdAt() == null) {
            return 0;
        }
        long days = ChronoUnit.DAYS.between(order.createdAt(), LocalDate.now());
        double score = Math.max(0, 1 - days / 60.0);
        if (score >= 0.7) {
            reasons.add("最近下单");
        }
        return score;
    }

    private static List<String> stringList(Object value) {
        if (value instanceof List<?> list) {
            List<String> result = new ArrayList<>();
            for (Object item : list) {
                if (item != null) {
                    result.add(String.valueOf(item));
                }
            }
            return result;
        }
        return List.of();
    }

    private static String stringValue(Object value) {
        return value == null || String.valueOf(value).isBlank() ? null : String.valueOf(value);
    }

    private static LocalDate date(Object value) {
        String text = stringValue(value);
        if (text == null) {
            return null;
        }
        try {
            return LocalDate.parse(text);
        } catch (DateTimeParseException exc) {
            throw new com.example.csagent.service.InvalidInputException("日期格式应为 yyyy-MM-dd: " + text);
        }
    }

    private static int intValue(Object value, int fallback) {
        if (value instanceof Number number) {
            return Math.min(10, Math.max(1, number.intValue()));
        }
        return fallback;
    }

    @Override
    public List<McpProtocol.ToolSpec> specs() {
        return List.of(new McpProtocol.ToolSpec(
                NAME,
                "按商品/时间/状态召回当前用户订单，返回带 score 与 reasons 的候选；用于用户只说商品名时定位订单",
                Map.of(
                        "type", "object",
                        "properties", Map.of(
                                "product_terms", Map.of(
                                        "type", "array",
                                        "items", Map.of("type", "string"),
                                        "description", "商品词，如 鞋、耳机、行李箱"),
                                "created_from", Map.of("type", "string", "description", "下单日期下限 yyyy-MM-dd"),
                                "created_to", Map.of("type", "string", "description", "下单日期上限 yyyy-MM-dd"),
                                "delivered_from", Map.of("type", "string", "description", "签收日期下限"),
                                "delivered_to", Map.of("type", "string", "description", "签收日期上限"),
                                "action", Map.of("type", "string", "enum",
                                        List.of("refund", "return", "exchange", "logistics", "query")),
                                "limit", Map.of("type", "integer", "minimum", 1, "maximum", 10)),
                        "additionalProperties", false),
                args -> findMyOrders(args)));
    }
}
