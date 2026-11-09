package com.example.csagent.mcp;

import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.security.JwtService;
import io.jsonwebtoken.Claims;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 从 Authorization 头解析 JWT，把用户放进 {@link McpAuthContext}。
 *
 * <p>只处理 MCP 端点；解析失败不在这里 401，而是由工具调用时统一报「缺少身份」，
 * 避免 MCP 协议层与 HTTP 鉴权层产生两份不一致的错误语义。
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 20)
public class McpAuthFilter extends OncePerRequestFilter {

    private final JwtService jwtService;

    public McpAuthFilter(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/mcp");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        if (header != null && header.regionMatches(true, 0, "Bearer ", 0, 7)) {
            try {
                Claims claims = jwtService.parse(header.substring(7).trim());
                McpAuthContext.set(new AuthenticatedUser(
                        claims.getSubject(),
                        ((Number) claims.get("userId")).longValue(),
                        String.valueOf(claims.get("role"))));
            } catch (RuntimeException ignored) {
                // 令牌无效：保持未认证，工具调用会明确拒绝
            }
        }
        try {
            filterChain.doFilter(request, response);
        } finally {
            McpAuthContext.clear();
        }
    }
}
