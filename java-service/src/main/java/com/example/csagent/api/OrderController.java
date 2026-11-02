package com.example.csagent.api;

import com.example.csagent.domain.Order;
import com.example.csagent.service.AuditLog;
import com.example.csagent.store.OrderStore;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderStore store;
    private final AuditLog audit;

    public OrderController(OrderStore store, AuditLog audit) {
        this.store = store;
        this.audit = audit;
    }

    @GetMapping("/{orderNo}")
    public Order get(@PathVariable String orderNo) {
        Order order = store.findOrder(orderNo)
                .orElseThrow(() -> new NotFoundException("订单不存在: " + orderNo));
        audit.record("ORDER_QUERY", order.orderNo(), Map.of("status", order.status()));
        return order;
    }
}
