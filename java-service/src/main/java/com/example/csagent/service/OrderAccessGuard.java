package com.example.csagent.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.api.NotFoundException;
import com.example.csagent.domain.OrderEntity;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.store.OrderMapper;
import org.springframework.stereotype.Service;

/**
 * 订单归属守卫：订单详情与物流查询共用同一套可见性规则。
 *
 * <p>越权与不存在抛<b>同一个</b> 404（消息不含订单号）；越权时额外写一条 DENIED 审计。
 * 买家查询在数据层带 {@code user_id} 条件；只有为了记审计才做一次存在性探测。
 */
@Service
public class OrderAccessGuard {

    /** 统一话术：订单与物流的越权/不存在都复用它。 */
    public static final String NOT_FOUND_MESSAGE = "订单不存在";

    private final OrderMapper orderMapper;
    private final AuditService auditService;

    public OrderAccessGuard(OrderMapper orderMapper, AuditService auditService) {
        this.orderMapper = orderMapper;
        this.auditService = auditService;
    }

    public OrderEntity requireVisible(String orderNo, AuthenticatedUser user, String action, String requestPath) {
        if (user.isCustomerServiceAgent()) {
            OrderEntity any = orderMapper.selectById(orderNo);
            if (any == null) {
                throw new NotFoundException(NOT_FOUND_MESSAGE);
            }
            return any;
        }

        OrderEntity own = orderMapper.selectOne(new LambdaQueryWrapper<OrderEntity>()
                .eq(OrderEntity::getOrderNo, orderNo)
                .eq(OrderEntity::getUserId, user.userId()));
        if (own != null) {
            return own;
        }

        if (orderMapper.selectById(orderNo) != null) {
            auditService.recordQuietly(AuditEvent.of(
                    user.username(), user.role(), action, AuditEvent.TYPE_ORDER,
                    orderNo, AuditEvent.RESULT_DENIED, requestPath));
        }
        throw new NotFoundException(NOT_FOUND_MESSAGE);
    }
}
