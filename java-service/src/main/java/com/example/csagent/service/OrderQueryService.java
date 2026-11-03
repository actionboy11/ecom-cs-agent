package com.example.csagent.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.domain.Order;
import com.example.csagent.domain.OrderEntity;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.store.OrderMapper;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 订单查询：详情与列表。
 * 可见性规则统一走 {@link OrderAccessGuard}；列表在数据层按 user_id 过滤（坐席除外）。
 */
@Service
public class OrderQueryService {

    private final OrderMapper orderMapper;
    private final OrderAccessGuard orderAccessGuard;
    private final AuditService auditService;

    public OrderQueryService(OrderMapper orderMapper, OrderAccessGuard orderAccessGuard, AuditService auditService) {
        this.orderMapper = orderMapper;
        this.orderAccessGuard = orderAccessGuard;
        this.auditService = auditService;
    }

    public Order findByOrderNo(String orderNo, AuthenticatedUser user, String requestPath) {
        OrderEntity entity = orderAccessGuard.requireVisible(
                orderNo, user, AuditEvent.ACTION_QUERY_ORDER, AuditEvent.TYPE_ORDER, requestPath);
        Order order = toOrder(entity);
        auditService.recordQuietly(AuditEvent.of(
                user.username(), user.role(), AuditEvent.ACTION_QUERY_ORDER,
                AuditEvent.TYPE_ORDER, orderNo, AuditEvent.RESULT_OK, requestPath));
        return order;
    }

    public List<Order> listFor(AuthenticatedUser user, String requestPath) {
        LambdaQueryWrapper<OrderEntity> query = new LambdaQueryWrapper<OrderEntity>()
                .orderByAsc(OrderEntity::getCreatedAt)
                .orderByAsc(OrderEntity::getOrderNo);
        if (!user.isCustomerServiceAgent()) {
            query.eq(OrderEntity::getUserId, user.userId());
        }
        List<Order> orders = orderMapper.selectList(query).stream().map(OrderQueryService::toOrder).toList();
        // 列表也要留痕：坐席能列举全部订单，必须可追溯（T05 AC）
        auditService.recordQuietly(AuditEvent.of(
                user.username(), user.role(), AuditEvent.ACTION_QUERY_ORDER_LIST,
                AuditEvent.TYPE_ORDER, "-", AuditEvent.RESULT_OK, requestPath,
                java.util.Map.of("returned", orders.size())));
        return orders;
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
