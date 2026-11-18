package com.example.csagent.service;

import com.example.csagent.config.EvalClock;
import com.example.csagent.domain.Order;
import com.example.csagent.security.AuthenticatedUser;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 运输中拦截：有物流记录才模拟拦截成功，否则失败并转人工。 */
@Service
public class InterceptService {

    private final JdbcTemplate jdbc;
    private final OrderQueryService orderQueryService;
    private final OrderEligibilityService eligibilityService;
    private final EvalClock clock;

    public InterceptService(
            JdbcTemplate jdbc,
            OrderQueryService orderQueryService,
            OrderEligibilityService eligibilityService,
            EvalClock clock) {
        this.jdbc = jdbc;
        this.orderQueryService = orderQueryService;
        this.eligibilityService = eligibilityService;
        this.clock = clock;
    }

    @Transactional
    public Map<String, Object> intercept(String orderNo, AuthenticatedUser user, String path) {
        Order order = orderQueryService.findByOrderNo(orderNo, user, path);
        if (!"已发货".equals(order.status()) && !"运输中".equals(order.status())) {
            throw new StateConflictException("当前订单状态不需要拦截");
        }
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT carrier, tracking_no FROM logistics WHERE order_no = ? LIMIT 1", orderNo);
        boolean canIntercept = !rows.isEmpty()
                && rows.get(0).get("tracking_no") != null
                && !String.valueOf(rows.get(0).get("tracking_no")).isBlank();
        String status = canIntercept ? "INTERCEPTED" : "FAILED";
        String failure = canIntercept ? null : "暂无有效物流单号，无法拦截";
        String carrier = rows.isEmpty() ? null : String.valueOf(rows.get(0).get("carrier"));
        String tracking = rows.isEmpty() ? null : String.valueOf(rows.get(0).get("tracking_no"));
        jdbc.update("""
                INSERT INTO order_intercepts
                    (order_no, user_id, status, carrier, tracking_no, failure_reason)
                VALUES (?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE status=VALUES(status), carrier=VALUES(carrier),
                    tracking_no=VALUES(tracking_no), failure_reason=VALUES(failure_reason),
                    updated_at=CURRENT_TIMESTAMP
                """, orderNo, user.userId(), status, carrier, tracking, failure);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("orderNo", orderNo);
        result.put("status", status);
        result.put("carrier", carrier);
        result.put("trackingNo", tracking);
        result.put("failureReason", failure);
        return result;
    }

    public Map<String, Object> get(String orderNo, AuthenticatedUser user, String path) {
        Order order = orderQueryService.findByOrderNo(orderNo, user, path);
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT status, carrier, tracking_no, failure_reason FROM order_intercepts WHERE order_no = ?",
                orderNo);
        if (rows.isEmpty()) {
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("orderNo", orderNo);
            result.put("status", "NONE");
            return result;
        }
        Map<String, Object> row = rows.get(0);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("orderNo", orderNo);
        result.put("status", row.get("status"));
        result.put("carrier", row.get("carrier"));
        result.put("trackingNo", row.get("tracking_no"));
        result.put("failureReason", row.get("failure_reason"));
        return result;
    }

    public boolean intercepted(String orderNo) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM order_intercepts WHERE order_no = ? AND status = 'INTERCEPTED'",
                Integer.class, orderNo);
        return count != null && count > 0;
    }
}
