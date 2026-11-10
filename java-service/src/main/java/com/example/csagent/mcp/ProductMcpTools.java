package com.example.csagent.mcp;

import com.example.csagent.api.NotFoundException;
import com.example.csagent.domain.Product;
import com.example.csagent.store.ProductStore;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/** MCP 工具：商品查询（SPEC §7.1 `get_product_info`，支持 sku 或关键词）。 */
@Component
public class ProductMcpTools implements McpTool {

    public static final String NAME = "get_product_info";

    private final ProductStore productStore;
    private final ObjectMapper objectMapper;

    public ProductMcpTools(ProductStore productStore, ObjectMapper objectMapper) {
        this.productStore = productStore;
        this.objectMapper = objectMapper;
    }

    public String getProductInfo(String sku, String keyword) throws Exception {
        if (sku != null && !sku.isBlank()) {
            Product product = productStore.find(sku)
                    .orElseThrow(() -> new NotFoundException("商品不存在"));
            return objectMapper.writeValueAsString(product);
        }
        if (keyword == null || keyword.isBlank()) {
            throw new MissingSlotException("MISSING_SLOT: 需要 sku 或 keyword");
        }
        List<Product> products = productStore.search(keyword);
        return objectMapper.writeValueAsString(products);
    }

    @Override
    public List<McpProtocol.ToolSpec> specs() {
        return List.of(new McpProtocol.ToolSpec(
                NAME,
                "查询商品信息：给 sku 查详情，给关键词做搜索",
                Map.of(
                        "type", "object",
                        "properties", Map.of(
                                "sku", Map.of("type", "string", "description", "商品编码"),
                                "keyword", Map.of("type", "string", "description", "关键词")),
                        "additionalProperties", false),
                args -> getProductInfo((String) args.get("sku"), (String) args.get("keyword"))));
    }
}
