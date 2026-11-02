package com.example.csagent.domain;

import java.util.List;

public record Logistics(
        String orderNo,
        String carrier,
        String trackingNo,
        String status,
        List<String> traces
) {
}
