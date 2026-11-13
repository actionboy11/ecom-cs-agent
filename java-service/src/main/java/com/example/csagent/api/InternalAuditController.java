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

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;

/**
 * 内部审计写入接口：供 Agent（Python）上报**会话越权**事件。
 *
 * <p>安全约束（评审后收窄）：
 * <ul>
 *   <li>只允许写 `THREAD_ACCESS / DENIED / THREAD`，其它 action 一律 400，
 *       避免持有内部令牌的调用方伪造 `LOGIN` 等审计；</li>
 *   <li>path 必须是 `/api/v1/` 开头的业务路径，防止写入假的请求路径；</li>
 *   <li>detail 只接受 `reason` 一个字段，不接收对话正文；</li>
 *   <li>令牌常量时间比较；未配置令牌时一律 401。</li>
 * </ul>
 */
@RestController
@RequestMapping("/api/internal")
public class InternalAuditController {

    static final String ALLOWED_ACTION = "THREAD_ACCESS";
    static final String ALLOWED_RESOURCE = "THREAD";
    static final String ALLOWED_RESULT = "DENIED";

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
        if (!tokenMatches(token)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error", "UNAUTHORIZED", "message", "内部审计令牌无效"));
        }
        String invalid = validate(request);
        if (invalid != null) {
            return ResponseEntity.badRequest().body(Map.of("error", "BAD_REQUEST", "message", invalid));
        }
        auditService.recordQuietly(AuditEvent.of(
                clip(request.actor().trim()), request.actorRole() == null ? "" : clip(request.actorRole()),
                ALLOWED_ACTION, ALLOWED_RESOURCE, clip(request.resourceId()), ALLOWED_RESULT,
                request.path(), Map.of("reason", reasonOf(request.detail()))));
        return ResponseEntity.ok(Map.of("status", "recorded"));
    }

    /** 审计列是 VARCHAR(50)：超长会插入失败并被静默吞掉，这里先截断。 */
    private static String clip(String value) {
        return value == null || value.length() <= 50 ? value : value.substring(0, 50);
    }

    private boolean tokenMatches(String token) {
        if (expectedToken.isBlank() || token == null) {
            return false;
        }
        return MessageDigest.isEqual(
                expectedToken.getBytes(StandardCharsets.UTF_8), token.getBytes(StandardCharsets.UTF_8));
    }

    private String validate(InternalAuditRequest request) {
        if (request.actor() == null || request.actor().isBlank()) {
            return "actor 不能为空";
        }
        if (request.resourceId() == null || request.resourceId().isBlank()) {
            return "resourceId 不能为空";
        }
        if (!ALLOWED_ACTION.equals(request.action())
                || !ALLOWED_RESOURCE.equals(request.resourceType())
                || !ALLOWED_RESULT.equals(request.result())) {
            return "该接口只接受 THREAD_ACCESS / THREAD / DENIED";
        }
        if (request.path() == null || !request.path().startsWith("/api/v1/")) {
            return "path 必须是 /api/v1/ 开头的业务路径";
        }
        return null;
    }

    private String reasonOf(Map<String, Object> detail) {
        Object reason = detail == null ? null : detail.get("reason");
        return reason == null ? "not_owner" : String.valueOf(reason);
    }
}
