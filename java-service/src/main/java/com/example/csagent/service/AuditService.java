package com.example.csagent.service;

import com.example.csagent.domain.AuditLogEntity;
import com.example.csagent.store.AuditLogMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * 写审计。只记录操作元数据，调用方负责保证 detail 里不含对话正文。
 */
@Service
public class AuditService {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final AuditLogMapper auditLogMapper;

    public AuditService(AuditLogMapper auditLogMapper) {
        this.auditLogMapper = auditLogMapper;
    }

    public void record(AuditEvent event) {
        AuditLogEntity entry = new AuditLogEntity();
        entry.setTs(LocalDateTime.now());
        entry.setActor(event.actor());
        entry.setActorRole(event.actorRole());
        entry.setAction(event.action());
        entry.setResourceType(event.resourceType());
        entry.setResourceId(event.resourceId());
        entry.setResult(event.result());
        entry.setDetail(toJson(event));
        auditLogMapper.insert(entry);
    }

    private static String toJson(AuditEvent event) {
        if (event.detail() == null || event.detail().isEmpty()) {
            return null;
        }
        try {
            return MAPPER.writeValueAsString(event.detail());
        } catch (JsonProcessingException ex) {
            // detail 是可选的调试信息，序列化失败不应影响主流程
            return null;
        }
    }
}
