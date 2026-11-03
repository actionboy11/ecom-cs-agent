package com.example.csagent.service;

import com.example.csagent.api.NotFoundException;
import com.example.csagent.domain.Order;
import com.example.csagent.domain.OrderEntity;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.store.OrderMapper;
import org.springframework.stereotype.Service;

/**
 * 订单查询。
 *
 * <p>越权与不存在返回<b>完全相同</b>的 404（消息里不带订单号），
 * 外部无法通过状态码或响应体判断资源是否存在（ADR-0001）。
 */
@Service
public class OrderQueryService {

    /** 统一话术：越权与不存在共用，避免泄露资源存在性。 */
    private static final String NOT_FOUND_MESSAGE = "订单不存在";

    private final OrderMapper orderMapper;
    private final AuditService auditService;

    public OrderQueryService(OrderMapper orderMapper, AuditService auditService) {
        this.orderMapper = orderMapper;
        this.auditService = auditService;
    }

    public Order findByOrderNo(String orderNo, AuthenticatedUser user) {
        OrderEntity entity = orderMapper.selectById(orderNo);
        if (entity == null) {
            throw new NotFoundException(NOT_FOUND_MESSAGE);
        }

        boolean ownOrder = entity.getUserId() != null && entity.getUserId() == user.userId();
        if (!ownOrder && !user.isCustomerServiceAgent()) {
            auditService.record(new AuditEvent(
                    user.username(), user.role(),
                    AuditEvent.ACTION_QUERY_ORDER, AuditEvent.TYPE_ORDER, orderNo, AuditEvent.RESULT_DENIED));
            throw new NotFoundException(NOT_FOUND_MESSAGE);
        }

        Order order = toOrder(entity);
        // 先组装返回值再写审计：避免审计成功但响应构造失败时留下虚假的 OK 记录
        auditService.record(new AuditEvent(
                user.username(), user.role(),
                AuditEvent.ACTION_QUERY_ORDER, AuditEvent.TYPE_ORDER, orderNo, AuditEvent.RESULT_OK));
        return order;
    }

    public long count() {
        return orderMapper.selectCount(null);
    }

    private static Order toOrder(OrderEntity entity) {
        return new Order(
                entity.getOrderNo(),
                entity.getItemName(),
                entity.getAmount(),
                entity.getStatus(),
                entity.getCreatedAt().toLocalDate());
    }
}
