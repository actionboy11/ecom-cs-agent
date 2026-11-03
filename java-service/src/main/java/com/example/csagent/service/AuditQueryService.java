package com.example.csagent.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.api.AuditRecord;
import com.example.csagent.domain.AuditLogEntity;
import com.example.csagent.store.AuditLogMapper;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 读审计（仅坐席可用）。按写入顺序（自增 id）倒序，最近写入的在前。
 */
@Service
public class AuditQueryService {

    private final AuditLogMapper auditLogMapper;

    public AuditQueryService(AuditLogMapper auditLogMapper) {
        this.auditLogMapper = auditLogMapper;
    }

    public List<AuditRecord> recent(int limit) {
        int safeLimit = Math.min(Math.max(limit, 1), 100);
        return auditLogMapper.selectList(new LambdaQueryWrapper<AuditLogEntity>()
                        .orderByDesc(AuditLogEntity::getId)
                        .last("limit " + safeLimit))
                .stream()
                .map(AuditRecord::from)
                .toList();
    }
}
