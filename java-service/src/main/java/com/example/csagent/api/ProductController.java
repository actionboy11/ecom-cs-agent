package com.example.csagent.api;

import com.example.csagent.domain.Product;
import com.example.csagent.store.ProductStore;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 商品信息是公开数据，不需要令牌（SPEC §2）。
 * 公开只读接口不写审计——审计只记录「身份对资源做了什么」，匿名浏览没有可追责的主体。
 */
@RestController
@RequestMapping("/api/products")
public class ProductController {

    private final ProductStore store;

    public ProductController(ProductStore store) {
        this.store = store;
    }

    @GetMapping("/{sku}")
    public Product get(@PathVariable String sku) {
        return store.find(sku)
                .orElseThrow(() -> new NotFoundException("商品不存在: " + sku));
    }

    /** 按名称或 SKU 搜索；用户往往只知道商品名，不知道 SKU。 */
    @GetMapping("/search")
    public List<Product> search(@RequestParam(name = "keyword", required = false) String keyword) {
        return store.search(keyword == null ? "" : keyword);
    }
}
