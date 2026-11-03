package com.example.csagent.service;

import java.util.Map;

/**
 * 一条审计事实：谁、对哪个资源、做了什么、结果如何，以及请求路径。
 * 用记录类型替代一长串位置参数，避免调用点把字段顺序写错。
 *
 * <p>detail 只放请求元数据（如 path），<b>不放对话正文</b>（ADR-0005）。
 */
public record AuditEvent(String actor, String actorRole, String action,
                          String resourceType, String resourceId, String result,
                          Map<String, Object> detail) {

    public static final String RESULT_OK = "OK";
    public static final String RESULT_DENIED = "DENIED";

    public static final String ACTION_QUERY_ORDER = "QUERY_ORDER";
    public static final String ACTION_QUERY_LOGISTICS = "QUERY_LOGISTICS";
    public static final String ACTION_APPLY_AFTER_SALES = "APPLY_AFTER_SALES";

    public static final String TYPE_ORDER = "ORDER";
    public static final String TYPE_LOGISTICS = "LOGISTICS";
    public static final String TYPE_AFTER_SALES = "AFTER_SALES";

    public static AuditEvent of(String actor, String actorRole, String action,
                                String resourceType, String resourceId, String result,
                                String requestPath) {
        Map<String, Object> detail = requestPath == null || requestPath.isBlank()
                ? Map.of()
                : Map.of("path", requestPath);
        return new AuditEvent(actor, actorRole, action, resourceType, resourceId, result, detail);
    }
}
