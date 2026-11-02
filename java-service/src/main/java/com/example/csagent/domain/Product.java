package com.example.csagent.domain;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 商品信息。字段与 Python 侧 schemas.ProductInfo 对应。
 */
public record Product(
        String sku,
        String name,
        BigDecimal price,
        Map<String, String> attrs,
        int stock,
        List<String> faq
) {
}
