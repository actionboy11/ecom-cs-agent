package com.example.csagent.api;

import java.util.List;

public record OrderPage(
        List<com.example.csagent.domain.Order> items,
        long total,
        int page,
        int pageSize,
        boolean hasMore
) {
}
