package com.example.csagent.api;

import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.AuditEvent;
import com.example.csagent.service.AuditQueryService;
import com.example.csagent.service.AuditService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 审计查询：仅坐席可访问（角色限制在 SecurityConfig 中统一声明）。
 * 「谁看了审计」本身也留痕——审计工具自己也要可追责。
 */
@RestController
@RequestMapping("/api/audit")
public class AuditController {

    private final AuditQueryService auditQueryService;
    private final AuditService auditService;

    public AuditController(AuditQueryService auditQueryService, AuditService auditService) {
        this.auditQueryService = auditQueryService;
        this.auditService = auditService;
    }

    @GetMapping
    public List<AuditRecord> recent(@RequestParam(defaultValue = "20") int limit,
                                    @AuthenticationPrincipal AuthenticatedUser user,
                                    HttpServletRequest request) {
        List<AuditRecord> records = auditQueryService.recent(limit);
        auditService.recordQuietly(AuditEvent.of(
                user.username(), user.role(), AuditEvent.ACTION_READ_AUDIT, AuditEvent.TYPE_AUDIT,
                "-", AuditEvent.RESULT_OK, request.getRequestURI(), Map.of("returned", records.size())));
        return records;
    }
}
