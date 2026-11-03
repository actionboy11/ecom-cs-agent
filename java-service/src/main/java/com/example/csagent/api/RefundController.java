package com.example.csagent.api;

import com.example.csagent.domain.Refund;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.AuditEvent;
import com.example.csagent.service.AuditService;
import com.example.csagent.service.OrderAccessGuard;
import com.example.csagent.store.OrderStore;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/refunds")
public class RefundController {

    private final OrderStore store;
    private final OrderAccessGuard orderAccessGuard;
    private final AuditService auditService;

    public RefundController(OrderStore store, OrderAccessGuard orderAccessGuard, AuditService auditService) {
        this.store = store;
        this.orderAccessGuard = orderAccessGuard;
        this.auditService = auditService;
    }

    @PostMapping
    public Refund create(@Valid @RequestBody RefundRequest request,
                         @AuthenticationPrincipal AuthenticatedUser user,
                         HttpServletRequest httpRequest) {
        // 只能对自己可见的订单发起售后：越权与不存在同为 404（ADR-0001）
        orderAccessGuard.requireVisible(request.orderNo(), user,
                AuditEvent.ACTION_APPLY_AFTER_SALES, AuditEvent.TYPE_AFTER_SALES, httpRequest.getRequestURI());

        Refund refund = store.createRefund(request.orderNo(), request.reason());
        auditService.recordQuietly(AuditEvent.of(
                user.username(), user.role(),
                AuditEvent.ACTION_APPLY_AFTER_SALES, AuditEvent.TYPE_AFTER_SALES,
                refund.refundNo(), AuditEvent.RESULT_OK, httpRequest.getRequestURI()));
        return refund;
    }

    @GetMapping
    public List<Refund> list() {
        return store.findRefunds();
    }
}
