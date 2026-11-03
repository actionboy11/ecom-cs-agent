package com.example.csagent.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.api.NotFoundException;
import com.example.csagent.domain.Logistics;
import com.example.csagent.domain.LogisticsEntity;
import com.example.csagent.domain.LogisticsTraceEntity;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.store.LogisticsMapper;
import com.example.csagent.store.LogisticsTraceMapper;
import org.springframework.stereotype.Service;

import java.time.format.DateTimeFormatter;
import java.util.List;

/**
 * 物流查询：可见性沿用订单的归属规则，轨迹按 seq 升序返回。
 */
@Service
public class LogisticsQueryService {

    private static final DateTimeFormatter TRACE_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
    private static final String NO_LOGISTICS_MESSAGE = "物流信息不存在";

    private final LogisticsMapper logisticsMapper;
    private final LogisticsTraceMapper traceMapper;
    private final OrderAccessGuard orderAccessGuard;
    private final AuditService auditService;

    public LogisticsQueryService(LogisticsMapper logisticsMapper,
                                 LogisticsTraceMapper traceMapper,
                                 OrderAccessGuard orderAccessGuard,
                                 AuditService auditService) {
        this.logisticsMapper = logisticsMapper;
        this.traceMapper = traceMapper;
        this.orderAccessGuard = orderAccessGuard;
        this.auditService = auditService;
    }

    public Logistics findByOrderNo(String orderNo, AuthenticatedUser user, String requestPath) {
        orderAccessGuard.requireVisible(
                orderNo, user, AuditEvent.ACTION_QUERY_LOGISTICS, AuditEvent.TYPE_LOGISTICS, requestPath);

        LogisticsEntity head = logisticsMapper.selectById(orderNo);
        if (head == null) {
            throw new NotFoundException(NO_LOGISTICS_MESSAGE);
        }

        // 按时间升序（seq 只作为同一时刻的稳定次序），与 SPEC「轨迹按时间升序」一致
        List<String> traces = traceMapper.selectList(new LambdaQueryWrapper<LogisticsTraceEntity>()
                        .eq(LogisticsTraceEntity::getOrderNo, orderNo)
                        .orderByAsc(LogisticsTraceEntity::getTraceTime)
                        .orderByAsc(LogisticsTraceEntity::getSeq))
                .stream()
                .map(trace -> trace.getTraceTime().format(TRACE_FORMAT) + " " + trace.getContent())
                .toList();

        Logistics logistics = new Logistics(
                head.getOrderNo(), head.getCarrier(), head.getTrackingNo(), head.getStatus(), traces);

        auditService.recordQuietly(AuditEvent.of(
                user.username(), user.role(), AuditEvent.ACTION_QUERY_LOGISTICS,
                AuditEvent.TYPE_LOGISTICS, orderNo, AuditEvent.RESULT_OK, requestPath));
        return logistics;
    }
}
