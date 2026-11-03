package com.example.csagent.service;

import com.example.csagent.api.NotFoundException;
import com.example.csagent.domain.Order;
import com.example.csagent.domain.OrderEntity;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.store.OrderMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * 订单查询。
 *
 * <p>三条硬约束：
 * <ol>
 *   <li>买家查询在<b>数据层</b>带 {@code user_id} 条件，不靠应用层事后判断；</li>
 *   <li>越权与不存在返回<b>完全相同</b>的 404（消息不带订单号），外部无法区分（ADR-0001）；</li>
 *   <li>审计写入失败不影响业务结果，否则「审计挂了」会变成新的存在性探针。</li>
 * </ol>
 */
@Service
public class OrderQueryService {

    private static final Logger log = LoggerFactory.getLogger(OrderQueryService.class);

    /** 统一话术：越权与不存在共用，避免泄露资源存在性。 */
    private static final String NOT_FOUND_MESSAGE = "订单不存在";

    private final OrderMapper orderMapper;
    private final AuditService auditService;

    public OrderQueryService(OrderMapper orderMapper, AuditService auditService) {
        this.orderMapper = orderMapper;
        this.auditService = auditService;
    }

    public Order findByOrderNo(String orderNo, AuthenticatedUser user, String requestPath) {
        if (user.isCustomerServiceAgent()) {
            OrderEntity entity = orderMapper.selectById(orderNo);
            if (entity == null) {
                throw new NotFoundException(NOT_FOUND_MESSAGE);
            }
            Order order = toOrder(entity);
            auditQuietly(user, AuditEvent.RESULT_OK, orderNo, requestPath);
            return order;
        }

        // 买家：查询条件里直接带 user_id，越权订单在数据层就查不出来
        OrderEntity own = orderMapper.selectOne(new LambdaQueryWrapper<OrderEntity>()
                .eq(OrderEntity::getOrderNo, orderNo)
                .eq(OrderEntity::getUserId, user.userId()));
        if (own != null) {
            Order order = toOrder(own);
            auditQuietly(user, AuditEvent.RESULT_OK, orderNo, requestPath);
            return order;
        }

        // 只有为了区分「记录的越权」与「压根不存在」才做一次存在性探测；
        // 探测结果不进入响应，只用来决定是否写 DENIED 审计。
        if (orderMapper.selectById(orderNo) != null) {
            auditQuietly(user, AuditEvent.RESULT_DENIED, orderNo, requestPath);
        }
        throw new NotFoundException(NOT_FOUND_MESSAGE);
    }

    public long count() {
        return orderMapper.selectCount(null);
    }

    private void auditQuietly(AuthenticatedUser user, String result, String orderNo, String requestPath) {
        try {
            auditService.record(AuditEvent.of(
                    user.username(), user.role(),
                    AuditEvent.ACTION_QUERY_ORDER, AuditEvent.TYPE_ORDER, orderNo, result, requestPath));
        } catch (RuntimeException ex) {
            log.warn("审计写入失败，已忽略以保证响应一致: {}", ex.getMessage());
        }
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
