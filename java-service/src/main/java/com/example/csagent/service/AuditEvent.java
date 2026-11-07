package com.example.csagent.service;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 一条审计事实：谁、对哪个资源、做了什么、结果如何，以及请求路径与附加元数据。
 * 用记录类型替代一长串位置参数，避免调用点把字段顺序写错。
 *
 * <p>detail 只放请求元数据（如 path、count），<b>不放对话正文</b>（ADR-0005）。
 */
public record AuditEvent(String actor, String actorRole, String action,
                          String resourceType, String resourceId, String result,
                          Map<String, Object> detail) {

    public static final String RESULT_OK = "OK";
    public static final String RESULT_DENIED = "DENIED";

    public static final String ACTION_QUERY_ORDER = "QUERY_ORDER";
    public static final String ACTION_QUERY_ORDER_LIST = "QUERY_ORDER_LIST";
    public static final String ACTION_QUERY_LOGISTICS = "QUERY_LOGISTICS";
    public static final String ACTION_APPLY_AFTER_SALES = "APPLY_AFTER_SALES";
    public static final String ACTION_QUERY_AFTER_SALES_LIST = "QUERY_AFTER_SALES_LIST";
    public static final String ACTION_REVIEW_AFTER_SALES = "REVIEW_AFTER_SALES";
    public static final String ACTION_READ_AUDIT = "READ_AUDIT";

    public static final String TYPE_ORDER = "ORDER";
    public static final String TYPE_LOGISTICS = "LOGISTICS";
    public static final String TYPE_AFTER_SALES = "AFTER_SALES";
    public static final String TYPE_AUDIT = "AUDIT";

    public static AuditEvent of(String actor, String actorRole, String action,
                                String resourceType, String resourceId, String result,
                                String requestPath) {
        return of(actor, actorRole, action, resourceType, resourceId, result, requestPath, Map.of());
    }

    public static AuditEvent of(String actor, String actorRole, String action,
                                String resourceType, String resourceId, String result,
                                String requestPath, Map<String, Object> extra) {
        Map<String, Object> detail = new LinkedHashMap<>();
        if (requestPath != null && !requestPath.isBlank()) {
            detail.put("path", requestPath);
        }
        if (extra != null && !extra.isEmpty()) {
            detail.putAll(extra);
        }
        return new AuditEvent(actor, actorRole, action, resourceType, resourceId, result, detail);
    }
}
