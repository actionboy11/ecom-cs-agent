package com.example.csagent.service;

import com.example.csagent.domain.AfterSalesRequestEntity;
import com.example.csagent.domain.Refund;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.store.AfterSalesRequestMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 售后申请：落库 + 审计。
 *
 * <p>本切片只创建 REFUND 类型；类型扩展与审批在 S2-2。
 * 越权与不存在由 {@link OrderAccessGuard} 统一处理为 404（ADR-0001）。
 */
@Service
public class AfterSalesService {

    /** 请求号 = AS + 14 位时间戳 + 4 位随机数（定长 20，避免同秒并发撞主键）。 */
    private static final DateTimeFormatter REQUEST_NO_FORMAT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");
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

    @Transactional
    public Refund createRefund(String orderNo, String reason, AuthenticatedUser user, String requestPath) {
        orderAccessGuard.requireVisible(orderNo, user,
                AuditEvent.ACTION_APPLY_AFTER_SALES, AuditEvent.TYPE_AFTER_SALES, requestPath);

        LocalDateTime now = LocalDateTime.now().withNano(0);
        AfterSalesRequestEntity entity = new AfterSalesRequestEntity();
        entity.setRequestNo(nextRequestNo(now));
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
                Map.of("orderNo", orderNo, "status", entity.getStatus())));

        return new Refund(entity.getRequestNo(), orderNo, reason, entity.getStatus(), now);
    }

    private static String nextRequestNo(LocalDateTime now) {
        return "AS" + now.format(REQUEST_NO_FORMAT)
                + String.format("%04d", ThreadLocalRandom.current().nextInt(10_000));
    }
}
