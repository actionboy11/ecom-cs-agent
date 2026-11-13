package com.example.csagent.api;

import com.example.csagent.service.AuditEvent;
import com.example.csagent.service.AuditService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 内部审计写入接口：供 Agent（Python）上报越权等事件。
 *
 * <p>不是公开 API：必须携带内部令牌（`X-Internal-Token`），令牌为空时接口一律 401。
 * 审计只接收元数据，调用方不得传对话正文/密码/令牌（ADR-0005）。
 */
@RestController
@RequestMapping("/api/internal")
public class InternalAuditController {

    private final AuditService auditService;
    private final String expectedToken;

    public InternalAuditController(AuditService auditService,
                                   @Value("${app.internal-audit-token:}") String expectedToken) {
        this.auditService = auditService;
        this.expectedToken = expectedToken;
    }

    public record InternalAuditRequest(
            String actor,
            String actorRole,
            String action,
            String resourceType,
            String resourceId,
            String result,
            String path,
            Map<String, Object> detail
    ) {
    }

    @PostMapping("/audit")
    public ResponseEntity<Map<String, String>> record(
            @RequestHeader(name = "X-Internal-Token", required = false) String token,
            @RequestBody InternalAuditRequest request) {
        if (expectedToken.isBlank() || token == null || !expectedToken.equals(token)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error", "UNAUTHORIZED", "message", "内部审计令牌无效"));
        }
        auditService.recordQuietly(AuditEvent.of(
                request.actor(), request.actorRole(), request.action(), request.resourceType(),
                request.resourceId(), request.result(), request.path(),
                request.detail() == null ? Map.of() : request.detail()));
        return ResponseEntity.ok(Map.of("status", "recorded"));
    }
}
