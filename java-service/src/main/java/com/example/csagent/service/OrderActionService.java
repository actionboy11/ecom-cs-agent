package com.example.csagent.service;

import com.example.csagent.config.EvalClock;
import com.example.csagent.domain.Order;
import com.example.csagent.security.AuthenticatedUser;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/** 地址修改/发票申请：订单归属先走 OrderQueryService，业务状态由本服务校验。 */
@Service
public class OrderActionService {

    private final JdbcTemplate jdbc;
    private final OrderQueryService orderQueryService;
    private final OrderEligibilityService eligibilityService;
    private final EvalClock clock;

    public OrderActionService(
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
    public Map<String, Object> updateAddress(
            String orderNo, String receiver, String phone, String address,
            AuthenticatedUser user, String path) {
        Order order = orderQueryService.findByOrderNo(orderNo, user, path);
        if (!eligibilityService.check(order, "address", false, false, clock.today()).allowed()) {
            throw new StateConflictException("订单已发货或已签收，不能修改收货地址");
        }
        jdbc.update("""
                INSERT INTO order_addresses (order_no, user_id, receiver, phone, address)
                VALUES (?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE receiver=VALUES(receiver), phone=VALUES(phone),
                    address=VALUES(address), updated_at=CURRENT_TIMESTAMP
                """, orderNo, user.userId(), receiver, phone, address);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("orderNo", orderNo);
        result.put("receiver", receiver);
        result.put("phone", phone);
        result.put("address", address);
        result.put("status", "UPDATED");
        return result;
    }

    @Transactional
    public Map<String, Object> createInvoice(
            String orderNo, String title, String taxId, String email,
            AuthenticatedUser user, String path) {
        Order order = orderQueryService.findByOrderNo(orderNo, user, path);
        if (!eligibilityService.check(order, "invoice", false, false, clock.today()).allowed()) {
            throw new StateConflictException("订单未签收或签收超过 30 天，不能开票");
        }
        Integer exists = jdbc.queryForObject(
                "SELECT COUNT(*) FROM invoices WHERE order_no = ?", Integer.class, orderNo);
        if (exists != null && exists > 0) {
            throw new StateConflictException("该订单已提交过开票申请");
        }
        String invoiceNo = "INV" + UUID.randomUUID().toString().replace("-", "").substring(0, 16).toUpperCase();
        jdbc.update("""
                INSERT INTO invoices (invoice_no, order_no, user_id, title, tax_id, email, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)
                """, invoiceNo, orderNo, user.userId(), title, taxId, email, LocalDateTime.now());
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("invoiceNo", invoiceNo);
        result.put("orderNo", orderNo);
        result.put("status", "PENDING");
        return result;
    }
}
