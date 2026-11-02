package com.example.csagent.store;

import com.example.csagent.domain.Product;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 商品目录（内存版）。W3 换 MySQL，接口不变。
 * attrs 里的 key 会直接出现在 Agent 回复里，所以用中文 key，便于 RAG/生成引用。
 */
@Service
public class ProductStore {

    private final Map<String, Product> products = new ConcurrentHashMap<>();

    public ProductStore() {
        seed();
    }

    private void seed() {
        products.put("SKU1001", new Product(
                "SKU1001", "轻量跑步鞋 42码", new BigDecimal("399.00"),
                Map.of(
                        "材质", "网面透气",
                        "尺码建议", "偏大半码，建议选 41.5 码",
                        "适合", "大脚、宽脚人群",
                        "鞋底", "EVA 缓震中底"
                ),
                120,
                List.of("尺码偏大半码", "支持 7 天无理由退货")));

        products.put("SKU1002", new Product(
                "SKU1002", "主动降噪蓝牙耳机", new BigDecimal("299.00"),
                Map.of(
                        "续航", "30 小时（含充电仓）",
                        "编码", "支持 LDAC / AAC / SBC",
                        "降噪", "主动降噪 42dB",
                        "连接", "蓝牙 5.3，支持双设备"
                ),
                58,
                List.of("7 天无理由退货", "1 年质保")));

        products.put("SKU1003", new Product(
                "SKU1003", "20寸登机行李箱", new BigDecimal("699.00"),
                Map.of(
                        "材质", "PC+ABS 复合材质",
                        "轮子", "360° 万向轮",
                        "锁具", "TSA 海关锁",
                        "尺寸", "20 寸，可登机"
                ),
                34,
                List.of("可随身登机", "箱体 2 年保修")));
    }

    public Optional<Product> find(String sku) {
        return Optional.ofNullable(products.get(sku.toUpperCase()));
    }

    public List<Product> search(String keyword) {
        return products.values().stream()
                .filter(p -> p.name().contains(keyword) || p.sku().equalsIgnoreCase(keyword))
                .toList();
    }
}
