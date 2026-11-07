package com.example.csagent.service;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.example.csagent.api.NotFoundException;
import com.example.csagent.domain.AfterSalesRequest;
import com.example.csagent.domain.AfterSalesRequestEntity;
import com.example.csagent.domain.OrderEntity;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.store.AfterSalesRequestMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 售后申请与审批。
 *
 * <p>约束：
 * <ul>
 *   <li>只能对「自己可见的订单」发起售后，越权与不存在同为 404（ADR-0001）；</li>
 *   <li>{@code user_id} 记订单所有者，不是调用者；</li>
 *   <li>只有 PENDING 能被审批，已处理的再次审批抛冲突。</li>
 * </ul>
 */
@Service
public class AfterSalesService {

    private static final DateTimeFormatter REQUEST_NO_FORMAT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");
    private static final Set<String> VALID_TYPES = Set.of("REFUND", "RETURN", "EXCHANGE");
    private static final String STATUS_PENDING = "PENDING";
    private static final String STATUS_APPROVED = "APPROVED";
    private static final String STATUS_REJECTED = "REJECTED";

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
    public AfterSalesRequest create(String orderNo, String type, String reason,
                                    AuthenticatedUser user, String requestPath) {
        // 与 V3 的 ENUM('REFUND','RETURN','EXCHANGE') 保持一致；新增类型需同时改迁移与客户端
        String normalizedType = type == null ? "" : type.trim().toUpperCase(java.util.Locale.ROOT);
        if (!VALID_TYPES.contains(normalizedType)) {
            throw new IllegalArgumentException("不支持的售后类型: " + type);
        }

        OrderEntity order = orderAccessGuard.requireVisible(orderNo, user,
                AuditEvent.ACTION_APPLY_AFTER_SALES, AuditEvent.TYPE_AFTER_SALES, requestPath);

        LocalDateTime now = LocalDateTime.now().withNano(0);
        AfterSalesRequestEntity entity = new AfterSalesRequestEntity();
        entity.setRequestNo(nextRequestNo(now));
        entity.setOrderNo(orderNo);
        entity.setUserId(order.getUserId());
        entity.setType(normalizedType);
        entity.setReason(reason);
        entity.setStatus(STATUS_PENDING);
        entity.setCreatedAt(now);
        afterSalesMapper.insert(entity);

        auditService.recordQuietly(AuditEvent.of(
                user.username(), user.role(),
                AuditEvent.ACTION_APPLY_AFTER_SALES, AuditEvent.TYPE_AFTER_SALES,
                entity.getRequestNo(), AuditEvent.RESULT_OK, requestPath,
                Map.of("orderNo", orderNo, "type", normalizedType, "status", entity.getStatus())));

        return toView(entity);
    }

    @Transactional
    public AfterSalesRequest review(String requestNo, boolean approved, String note,
                                    AuthenticatedUser user, String requestPath) {
        if (afterSalesMapper.selectById(requestNo) == null) {
            throw new NotFoundException("售后申请不存在");
        }

        LocalDateTime now = LocalDateTime.now().withNano(0);
        String newStatus = approved ? STATUS_APPROVED : STATUS_REJECTED;

        // 条件更新：只有仍处于 PENDING 才能被改成终态，避免并发审批互相覆盖
        int updated = afterSalesMapper.update(null, new LambdaUpdateWrapper<AfterSalesRequestEntity>()
                .eq(AfterSalesRequestEntity::getRequestNo, requestNo)
                .eq(AfterSalesRequestEntity::getStatus, STATUS_PENDING)
                .set(AfterSalesRequestEntity::getStatus, newStatus)
                .set(AfterSalesRequestEntity::getReviewedBy, user.username())
                .set(AfterSalesRequestEntity::getReviewedAt, now)
                .set(AfterSalesRequestEntity::getReviewNote, note));
        if (updated == 0) {
            throw new StateConflictException("该售后申请已处理: " + requestNo);
        }

        auditService.recordQuietly(AuditEvent.of(
                user.username(), user.role(),
                AuditEvent.ACTION_REVIEW_AFTER_SALES, AuditEvent.TYPE_AFTER_SALES,
                requestNo, AuditEvent.RESULT_OK, requestPath,
                Map.of("approved", approved, "status", newStatus)));

        return toView(afterSalesMapper.selectById(requestNo));
    }

    private static AfterSalesRequest toView(AfterSalesRequestEntity entity) {
        return new AfterSalesRequest(
                entity.getRequestNo(), entity.getOrderNo(), entity.getType(), entity.getReason(),
                entity.getStatus(), entity.getCreatedAt(), entity.getReviewedBy(),
                entity.getReviewedAt(), entity.getReviewNote());
    }

    private static String nextRequestNo(LocalDateTime now) {
        return "AS" + now.format(REQUEST_NO_FORMAT)
                + String.format("%04d", ThreadLocalRandom.current().nextInt(10_000));
    }
}
