package com.example.csagent.domain;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 订单。字段名与 Python 侧 schemas.OrderInfo 一一对应，改动需两边同步。
 */
public record Order(
        String orderNo,
        String item,
        BigDecimal amount,
        String status,
        LocalDate createdAt
) {
}
