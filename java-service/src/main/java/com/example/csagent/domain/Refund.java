package com.example.csagent.domain;

import java.time.LocalDateTime;

public record Refund(
        String refundNo,
        String orderNo,
        String reason,
        String status,
        LocalDateTime createdAt
) {
}
