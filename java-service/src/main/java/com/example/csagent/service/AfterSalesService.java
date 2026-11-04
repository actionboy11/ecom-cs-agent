package com.example.csagent.service;

import com.example.csagent.domain.AfterSalesRequestEntity;
import com.example.csagent.domain.Refund;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.store.AfterSalesRequestMapper;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Map;

/**
 * 售后申请：落库 + 审计。
 *
 * <p>本切片只创建 REFUND 类型；类型扩展与审批在 S2-2。
 * 越权与不存在由 {@link OrderAccessGuard} 统一处理为 404（ADR-0001）。
 */
@Service
public class AfterSalesService {

    private static final DateTimeFormatter REQUEST_NO_FORMAT =
            DateTimeFormatter.ofPattern("yyyyMMddHHmmssSSS");
    private static final String TYPE_REFUND = "REFUND";
    private static final String STATUS_PENDING = "PENDING";

    private final AfterSalesRequestMapper afterSalesMapper;
    private final OrderAccessGuard orderAccessGuard;
    private final AuditService auditService;

    public AfterSalesService(AfterSalesRequestMapper afterSalesMapper,
                             OrderAccessGuard orderAccessGuard,
                             AuditService auditService) {
        this.afterSalesMapper = afterSalesMapper;
        this.orderAccessGuard = orderAccessGuard;
        this.auditService = auditService;
    }

    public Refund createRefund(String orderNo, String reason, AuthenticatedUser user, String requestPath) {
        orderAccessGuard.requireVisible(orderNo, user,
                AuditEvent.ACTION_APPLY_AFTER_SALES, AuditEvent.TYPE_AFTER_SALES, requestPath);

        LocalDateTime now = LocalDateTime.now().withNano(0);
        AfterSalesRequestEntity entity = new AfterSalesRequestEntity();
        entity.setRequestNo("AS" + now.format(REQUEST_NO_FORMAT));
        entity.setOrderNo(orderNo);
        entity.setUserId(user.userId());
        entity.setType(TYPE_REFUND);
        entity.setReason(reason);
        entity.setStatus(STATUS_PENDING);
        entity.setCreatedAt(now);
        afterSalesMapper.insert(entity);

        auditService.recordQuietly(AuditEvent.of(
                user.username(), user.role(),
                AuditEvent.ACTION_APPLY_AFTER_SALES, AuditEvent.TYPE_AFTER_SALES,
                entity.getRequestNo(), AuditEvent.RESULT_OK, requestPath,
                Map.of("orderNo", orderNo, "status", STATUS_PENDING)));

        return new Refund(entity.getRequestNo(), orderNo, reason, STATUS_PENDING, now);
    }
}
