package com.example.csagent.store;

import com.example.csagent.domain.Logistics;
import com.example.csagent.domain.Order;
import com.example.csagent.domain.Refund;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 内存版数据访问。W3 换成 MySQL + JPA，接口保持不变，所以 Agent 侧不用改。
 */
@Service
public class OrderStore {

    private final Map<String, Order> orders = new ConcurrentHashMap<>();
    private final Map<String, Logistics> logistics = new ConcurrentHashMap<>();
    private final List<Refund> refunds = new CopyOnWriteArrayList<>();
    private final AtomicInteger refundSeq = new AtomicInteger(1);

    public OrderStore() {
        seed();
    }

    private void seed() {
        orders.put("CS2024001", new Order(
                "CS2024001", "轻量跑步鞋 42码", new BigDecimal("399.00"),
                "已签收", LocalDate.of(2026, 10, 20)));
        orders.put("CS2024002", new Order(
                "CS2024002", "主动降噪蓝牙耳机", new BigDecimal("299.00"),
                "运输中", LocalDate.of(2026, 10, 28)));
        orders.put("CS2024003", new Order(
                "CS2024003", "20寸登机行李箱", new BigDecimal("699.00"),
                "已发货", LocalDate.of(2026, 11, 1)));

        logistics.put("CS2024001", new Logistics(
                "CS2024001", "顺丰速运", "SF1234567890", "已签收",
                List.of("2026-10-21 09:12 已揽收", "2026-10-22 15:40 运输中",
                        "2026-10-23 10:05 派送中", "2026-10-23 14:30 已签收")));
        logistics.put("CS2024002", new Logistics(
                "CS2024002", "中通快递", "ZT9876543210", "运输中",
                List.of("2026-10-29 08:00 已揽收", "2026-10-30 21:10 到达杭州转运中心")));
        logistics.put("CS2024003", new Logistics(
                "CS2024003", "京东物流", "JD5555666677", "已发货",
                List.of("2026-11-01 18:20 已出库")));
    }

    public Optional<Order> findOrder(String orderNo) {
        return Optional.ofNullable(orders.get(orderNo.toUpperCase()));
    }

    public Optional<Logistics> findLogistics(String orderNo) {
        return Optional.ofNullable(logistics.get(orderNo.toUpperCase()));
    }

    public Refund createRefund(String orderNo, String reason) {
        String normalized = orderNo.toUpperCase();
        Refund refund = new Refund(
                "RF" + LocalDate.now().getYear() + String.format("%04d", refundSeq.getAndIncrement()),
                normalized,
                reason,
                "PENDING",
                LocalDateTime.now().withNano(0));
        refunds.add(refund);
        return refund;
    }

    public List<Refund> findRefunds() {
        return List.copyOf(refunds);
    }

    public int orderCount() {
        return orders.size();
    }
}
