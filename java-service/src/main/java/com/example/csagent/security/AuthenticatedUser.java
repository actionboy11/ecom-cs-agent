package com.example.csagent.security;

/**
 * 认证成功后放进 SecurityContext 的身份主体。
 * 用记录类型替代散落的 Map detail，避免「userId 缺失就填 -1」这类哨兵值。
 */
public record AuthenticatedUser(String username, long userId, String role) {
}
