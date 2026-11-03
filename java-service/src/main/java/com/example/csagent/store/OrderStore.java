package com.example.csagent.store;

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
 * 售后写操作的临时内存实现（订单与物流已迁到 MySQL）。
 *
 * <p>注意：这里的订单种子仅用于退款流程的订单存在性校验，属于待收口的遗留路径——
 * 切片 2（售后请求建模）会把它整体替换为 MySQL。不要在此处新增业务数据。
 */
@Service
public class OrderStore {

    private final Map<String, Order> orders = new ConcurrentHashMap<>();
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
    }

    public Optional<Order> findOrder(String orderNo) {
        return Optional.ofNullable(orders.get(orderNo.toUpperCase()));
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
