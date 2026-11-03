package com.example.csagent.api;

import com.example.csagent.domain.Refund;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.AuditEvent;
import com.example.csagent.service.AuditService;
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
    private final AuditService auditService;

    public RefundController(OrderStore store, AuditService auditService) {
        this.store = store;
        this.auditService = auditService;
    }

    @PostMapping
    public Refund create(@Valid @RequestBody RefundRequest request,
                         @AuthenticationPrincipal AuthenticatedUser user,
                         HttpServletRequest httpRequest) {
        if (store.findOrder(request.orderNo()).isEmpty()) {
            throw new NotFoundException("订单不存在，无法申请退款: " + request.orderNo());
        }
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
