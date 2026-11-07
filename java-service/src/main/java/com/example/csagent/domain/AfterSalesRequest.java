package com.example.csagent.domain;

import java.time.LocalDateTime;

/**
 * 售后请求（退款 / 退货 / 换货统一建模，ADR-0004）。
 */
public record AfterSalesRequest(
        String requestNo,
        String orderNo,
        String type,
        String reason,
        String status,
        LocalDateTime createdAt,
        String reviewedBy,
        LocalDateTime reviewedAt
) {
}
