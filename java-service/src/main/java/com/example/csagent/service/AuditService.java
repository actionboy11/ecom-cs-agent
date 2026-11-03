package com.example.csagent.service;

import com.example.csagent.domain.AuditLogEntity;
import com.example.csagent.store.AuditLogMapper;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * 写审计。只记录操作元数据，调用方负责保证 detail 里不含对话正文。
 */
@Service
public class AuditService {

    private final AuditLogMapper auditLogMapper;

    public AuditService(AuditLogMapper auditLogMapper) {
        this.auditLogMapper = auditLogMapper;
    }

    public void record(String actor, String actorRole, String action,
                       String resourceType, String resourceId, String result) {
        AuditLogEntity entry = new AuditLogEntity();
        entry.setTs(LocalDateTime.now());
        entry.setActor(actor);
        entry.setActorRole(actorRole);
        entry.setAction(action);
        entry.setResourceType(resourceType);
        entry.setResourceId(resourceId);
        entry.setResult(result);
        auditLogMapper.insert(entry);
    }
}
