package com.example.csagent.api;

import com.example.csagent.domain.Refund;
import com.example.csagent.service.AuditLog;
import com.example.csagent.store.OrderStore;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/refunds")
public class RefundController {

    private final OrderStore store;
    private final AuditLog audit;

    public RefundController(OrderStore store, AuditLog audit) {
        this.store = store;
        this.audit = audit;
    }

    @PostMapping
    public Refund create(@Valid @RequestBody RefundRequest request) {
        if (store.findOrder(request.orderNo()).isEmpty()) {
            throw new NotFoundException("订单不存在，无法申请退款: " + request.orderNo());
        }
        Refund refund = store.createRefund(request.orderNo(), request.reason());
        audit.record("REFUND_APPLY", refund.refundNo(),
                Map.of("orderNo", refund.orderNo(), "status", refund.status()));
        return refund;
    }

    @GetMapping
    public List<Refund> list() {
        return store.findRefunds();
    }
}
