package com.example.csagent.api;

import com.example.csagent.service.AuditQueryService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 审计查询：仅坐席可访问（角色限制在 SecurityConfig 中统一声明）。
 */
@RestController
@RequestMapping("/api/audit")
public class AuditController {

    private final AuditQueryService auditQueryService;

    public AuditController(AuditQueryService auditQueryService) {
        this.auditQueryService = auditQueryService;
    }

    @GetMapping
    public List<AuditRecord> recent(@RequestParam(defaultValue = "50") int limit) {
        return auditQueryService.recent(limit);
    }
}
