package com.example.csagent.domain;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/** 商品信息。canonical 是短名，aliases 是用户可能说的同义/简称。 */
public record Product(
        String sku,
        String name,
        String canonical,
        BigDecimal price,
        Map<String, String> attrs,
        int stock,
        List<String> faq,
        List<String> aliases
) {
}
