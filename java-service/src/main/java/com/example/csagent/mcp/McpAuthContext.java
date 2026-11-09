package com.example.csagent.mcp;

import com.example.csagent.security.AuthenticatedUser;

/**
 * MCP 请求级身份上下文。
 *
 * <p>身份来源：HTTP 端点由 Spring Security 解析的登录用户注入；stdio 由进程启动参数
 * `MCP_USER_TOKEN` 注入。工具内部只能读取，**模型无法通过参数指定用户**。
 *
 * <p>令牌在注入时校验一次；这里额外记住过期时间，长驻进程里过期后调用会被拒绝。
 */
public final class McpAuthContext {

    private static final ThreadLocal<Holder> CURRENT = new ThreadLocal<>();

    private record Holder(AuthenticatedUser user, long expiresAtMillis) {
    }

    private McpAuthContext() {
    }

    public static void set(AuthenticatedUser user) {
        set(user, Long.MAX_VALUE);
    }

    public static void set(AuthenticatedUser user, long expiresAtMillis) {
        CURRENT.set(new Holder(user, expiresAtMillis));
    }

    public static AuthenticatedUser get() {
        Holder holder = CURRENT.get();
        return holder == null ? null : holder.user();
    }

    public static AuthenticatedUser require() {
        Holder holder = CURRENT.get();
        if (holder == null) {
            throw new IllegalStateException("UNAUTHORIZED: MCP 请求缺少身份");
        }
        if (System.currentTimeMillis() >= holder.expiresAtMillis()) {
            throw new IllegalStateException("UNAUTHORIZED: 令牌已过期");
        }
        return holder.user();
    }

    public static void clear() {
        CURRENT.remove();
    }
}
