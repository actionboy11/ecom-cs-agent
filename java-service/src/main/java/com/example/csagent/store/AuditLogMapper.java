package com.example.csagent.store;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.csagent.domain.AuditLogEntity;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AuditLogMapper extends BaseMapper<AuditLogEntity> {
}
