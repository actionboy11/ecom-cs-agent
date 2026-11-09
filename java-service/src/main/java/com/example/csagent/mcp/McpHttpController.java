package com.example.csagent.mcp;

import com.example.csagent.security.AuthenticatedUser;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * MCP 端点（HTTP JSON-RPC）。
 *
 * <p>与 stdio 共用 {@link McpProtocol}；身份来自 Spring Security 解析出的登录用户
 * （Authorization: Bearer），当前线程内注入 {@link McpAuthContext}，工具参数无法指定用户。
 */
@RestController
public class McpHttpController {

    private final McpToolRegistry registry;

    public McpHttpController(McpToolRegistry registry) {
        this.registry = registry;
    }

    @PostMapping(value = "/mcp", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> rpc(@RequestBody String body) {
        AuthenticatedUser user = currentUser();
        if (user == null) {
            return ResponseEntity.status(401)
                    .body("{\"jsonrpc\":\"2.0\",\"id\":null,\"error\":{\"code\":-32000,\"message\":\"UNAUTHORIZED\"}}");
        }
        McpAuthContext.set(user);
        try {
            McpProtocol.McpResponse response = registry.protocol().handle(body);
            return ResponseEntity.status(response.status())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(response.body());
        } finally {
            McpAuthContext.clear();
        }
    }

    private AuthenticatedUser currentUser() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof AuthenticatedUser user) {
            return user;
        }
        return null;
    }
}
