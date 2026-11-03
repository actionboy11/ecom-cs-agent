package com.example.csagent.api;

import com.example.csagent.domain.AuditLogEntity;

import java.time.LocalDateTime;

/**
 * 审计对外视图。detail 只含请求元数据（如 path），不含对话正文。
 */
public record AuditRecord(
        Long id,
        LocalDateTime ts,
        String actor,
        String actorRole,
        String action,
        String resourceType,
        String resourceId,
        String result,
        String detail
) {
    public static AuditRecord from(AuditLogEntity entity) {
        return new AuditRecord(
                entity.getId(), entity.getTs(), entity.getActor(), entity.getActorRole(),
                entity.getAction(), entity.getResourceType(), entity.getResourceId(),
                entity.getResult(), entity.getDetail());
    }
}
