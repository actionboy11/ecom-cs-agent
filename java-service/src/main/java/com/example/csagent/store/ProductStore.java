package com.example.csagent.store;

import com.example.csagent.domain.Product;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/** 商品目录（内存版）。canonical 是短名，aliases 供商品实体链接使用。 */
@Service
public class ProductStore {

    private final Map<String, Product> products = new ConcurrentHashMap<>();

    public ProductStore() {
        seed();
    }

    private void seed() {
        products.put("SKU1001", new Product(
                "SKU1001", "轻量跑步鞋 42码", "跑步鞋", new BigDecimal("399.00"),
                Map.of(
                        "材质", "网面透气",
                        "尺码建议", "偏大半码，建议选 41.5 码",
                        "适合", "大脚、宽脚人群",
                        "鞋底", "EVA 缓震中底"
                ),
                120,
                List.of("尺码偏大半码", "支持 7 天无理由退货"),
                List.of("跑步鞋", "跑鞋", "运动鞋", "鞋")
        ));

        products.put("SKU1002", new Product(
                "SKU1002", "主动降噪蓝牙耳机", "耳机", new BigDecimal("299.00"),
                Map.of(
                        "续航", "30 小时（含充电仓）",
                        "编码", "支持 LDAC / AAC / SBC",
                        "降噪", "主动降噪 42dB",
                        "连接", "蓝牙 5.3，支持双设备"
                ),
                58,
                List.of("7 天无理由退货", "1 年质保"),
                List.of("蓝牙耳机", "降噪耳机", "无线耳机", "耳机", "耳麦")
        ));

        products.put("SKU1003", new Product(
                "SKU1003", "20寸登机行李箱", "行李箱", new BigDecimal("699.00"),
                Map.of(
                        "材质", "PC+ABS 复合材料",
                        "轮子", "360° 万向轮",
                        "锁具", "TSA 海关锁",
                        "尺寸", "20 寸，可登机"
                ),
                34,
                List.of("可随身登机", "箱体 2 年保修"),
                List.of("行李箱", "登机箱", "箱子", "拉杆箱")
        ));

        products.put("SKU1004", new Product(
                "SKU1004", "316 不锈钢保温杯", "保温杯", new BigDecimal("129.00"),
                Map.of(
                        "容量", "500ml",
                        "材质", "316 不锈钢",
                        "保温", "12 小时"
                ),
                200,
                List.of("支持 7 天无理由退货"),
                List.of("保温杯", "水杯", "杯子", "杯")
        ));

        products.put("SKU1005", new Product(
                "SKU1005", "轻便双肩背包", "背包", new BigDecimal("259.00"),
                Map.of(
                        "容量", "20L",
                        "材质", "防泼水尼龙",
                        "背负", "透气肩带"
                ),
                80,
                List.of("支持 7 天无理由退货"),
                List.of("背包", "双肩包")
        ));

        products.put("SKU1006", new Product(
                "SKU1006", "20000mAh 充电宝", "充电宝", new BigDecimal("199.00"),
                Map.of(
                        "容量", "20000mAh",
                        "输出", "22.5W 快充",
                        "接口", "USB-C + USB-A"
                ),
                150,
                List.of("支持 7 天无理由退货"),
                List.of("充电宝", "移动电源")
        ));
    }

    public Optional<Product> find(String sku) {
        return Optional.ofNullable(products.get(sku.toUpperCase()));
    }

    public List<Product> search(String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return List.copyOf(products.values());
        }
        return products.values().stream()
                .filter(p -> p.name().contains(keyword)
                        || p.canonical().contains(keyword)
                        || p.aliases().contains(keyword)
                        || p.sku().equalsIgnoreCase(keyword))
                .toList();
    }
}
