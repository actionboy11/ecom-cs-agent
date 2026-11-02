package com.example.csagent.api;

import com.example.csagent.domain.Logistics;
import com.example.csagent.service.AuditLog;
import com.example.csagent.store.OrderStore;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/logistics")
public class LogisticsController {

    private final OrderStore store;
    private final AuditLog audit;

    public LogisticsController(OrderStore store, AuditLog audit) {
        this.store = store;
        this.audit = audit;
    }

    @GetMapping("/{orderNo}")
    public Logistics get(@PathVariable String orderNo) {
        Logistics info = store.findLogistics(orderNo)
                .orElseThrow(() -> new NotFoundException("暂无物流信息: " + orderNo));
        audit.record("LOGISTICS_QUERY", info.orderNo(), Map.of("status", info.status()));
        return info;
    }
}
