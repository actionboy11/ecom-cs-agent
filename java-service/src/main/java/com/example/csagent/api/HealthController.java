package com.example.csagent.api;

import com.example.csagent.store.OrderStore;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 健康检查。刻意不用 actuator：依赖更少，演示时也更容易解释。
 */
@RestController
@RequestMapping("/api/health")
public class HealthController {

    private final OrderStore store;

    public HealthController(OrderStore store) {
        this.store = store;
    }

    @GetMapping
    public Map<String, Object> health() {
        return Map.of(
                "status", "UP",
                "service", "cs-agent-service",
                "orders", store.orderCount()
        );
    }
}
