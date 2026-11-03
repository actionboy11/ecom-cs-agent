package com.example.csagent.service;

/**
 * 一条审计事实：谁、对哪个资源、做了什么、结果如何。
 * 用记录类型替代六个位置参数，避免调用点把字段顺序写错。
 */
public record AuditEvent(String actor, String actorRole, String action,
                          String resourceType, String resourceId, String result) {

    public static final String RESULT_OK = "OK";
    public static final String RESULT_DENIED = "DENIED";

    public static final String ACTION_QUERY_ORDER = "QUERY_ORDER";
    public static final String ACTION_QUERY_LOGISTICS = "QUERY_LOGISTICS";
    public static final String ACTION_APPLY_AFTER_SALES = "APPLY_AFTER_SALES";

    public static final String TYPE_ORDER = "ORDER";
    public static final String TYPE_LOGISTICS = "LOGISTICS";
    public static final String TYPE_AFTER_SALES = "AFTER_SALES";
}
