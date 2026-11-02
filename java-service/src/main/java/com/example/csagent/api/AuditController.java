package com.example.csagent.api;

import com.example.csagent.service.AuditLog;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 审计查询：演示时用来证明「Agent 的每次工具调用都被记录」。
 */
@RestController
@RequestMapping("/api/audit")
public class AuditController {

    private final AuditLog audit;

    public AuditController(AuditLog audit) {
        this.audit = audit;
    }

    @GetMapping
    public List<Map<String, Object>> recent(@RequestParam(defaultValue = "20") int limit) {
        return audit.recent(Math.min(Math.max(limit, 1), 100));
    }
}
