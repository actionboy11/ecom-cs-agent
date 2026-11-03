package com.example.csagent.security;

/**
 * 认证成功后放进 SecurityContext 的身份主体。
 * 用记录类型替代散落的 Map detail，避免「userId 缺失就填 -1」这类哨兵值。
 */
public record AuthenticatedUser(String username, long userId, String role) {

    /** 人工坐席角色。注意不是 AI Agent——领域词汇见 GLOSSARY.md。 */
    public static final String ROLE_CS_AGENT = "CS_AGENT";
    public static final String ROLE_CUSTOMER = "CUSTOMER";

    public boolean isCustomerServiceAgent() {
        return ROLE_CS_AGENT.equals(role);
    }
}
