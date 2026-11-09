package com.example.csagent.mcp;

import com.example.csagent.security.AuthenticatedUser;

/**
 * MCP 请求级身份上下文。
 *
 * <p>身份来自请求头 JWT（由 {@link McpAuthFilter} 解析），工具内部只能读取，
 * 模型无法通过工具参数指定用户——这是「身份不可由模型决定」在 MCP 侧的落地。
 */
public final class McpAuthContext {

    private static final ThreadLocal<AuthenticatedUser> CURRENT = new ThreadLocal<>();

    private McpAuthContext() {
    }

    public static void set(AuthenticatedUser user) {
        CURRENT.set(user);
    }

    public static AuthenticatedUser get() {
        return CURRENT.get();
    }

    public static AuthenticatedUser require() {
        AuthenticatedUser user = CURRENT.get();
        if (user == null) {
            throw new IllegalStateException("MCP 请求缺少身份：请携带 Authorization: Bearer <jwt>");
        }
        return user;
    }

    public static void clear() {
        CURRENT.remove();
    }
}
