package com.example.csagent.api;

import com.example.csagent.domain.Product;
import com.example.csagent.service.AuditLog;
import com.example.csagent.store.ProductStore;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/products")
public class ProductController {

    private final ProductStore store;
    private final AuditLog audit;

    public ProductController(ProductStore store, AuditLog audit) {
        this.store = store;
        this.audit = audit;
    }

    @GetMapping("/{sku}")
    public Product get(@PathVariable String sku) {
        Product product = store.find(sku)
                .orElseThrow(() -> new NotFoundException("商品不存在: " + sku));
        audit.record("PRODUCT_QUERY", product.sku(), Map.of("stock", product.stock()));
        return product;
    }
}
