package com.example.csagent.service;

import com.example.csagent.api.NotFoundException;
import com.example.csagent.domain.Order;
import com.example.csagent.domain.OrderEntity;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.store.OrderMapper;
import org.springframework.stereotype.Service;

/**
 * 订单查询。数据来自 MySQL（内存实现已退役）。
 * 归属校验在 T03 补上；本票只保证「身份 + 数据库」链路打通。
 */
@Service
public class OrderQueryService {

    private final OrderMapper orderMapper;
    private final AuditService auditService;

    public OrderQueryService(OrderMapper orderMapper, AuditService auditService) {
        this.orderMapper = orderMapper;
        this.auditService = auditService;
    }

    public Order findByOrderNo(String orderNo, AuthenticatedUser user) {
        OrderEntity entity = orderMapper.selectById(orderNo);
        if (entity == null) {
            throw new NotFoundException("订单不存在: " + orderNo);
        }
        auditService.record(user.username(), user.role(), "QUERY_ORDER", "ORDER", orderNo, "OK");
        return new Order(
                entity.getOrderNo(),
                entity.getItemName(),
                entity.getAmount(),
                entity.getStatus(),
                entity.getCreatedAt().toLocalDate());
    }

    public long count() {
        return orderMapper.selectCount(null);
    }
}
