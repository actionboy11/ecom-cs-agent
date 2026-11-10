package com.example.csagent.mcp;

import com.example.csagent.api.NotFoundException;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.ForbiddenOperationException;
import com.example.csagent.service.InvalidInputException;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** S5-2：物流与售后工具的权限口径。 */
@SpringBootTest
@ActiveProfiles("test")
class BusinessMcpToolsTest {

    @Autowired
    private LogisticsMcpTools logisticsTools;

    @Autowired
    private AfterSalesMcpTools afterSalesTools;

    @Autowired
    private ProductMcpTools productTools;

    @AfterEach
    void clearContext() {
        McpAuthContext.clear();
    }

    @Test
    void product_lookup_by_sku_returns_details() throws Exception {
        String json = productTools.getProductInfo("SKU1001", null);
        assertThat(json).contains("name");
    }

    @Test
    void product_requires_sku_or_keyword() {
        assertThatThrownBy(() -> productTools.getProductInfo(null, " "))
                .isInstanceOf(MissingSlotException.class);
    }

    @Test
    void logistics_returns_own_order_traces() throws Exception {
        McpAuthContext.set(new AuthenticatedUser("buyer_a", 1L, "CUSTOMER"));

        String json = logisticsTools.queryLogistics("CS2024001");

        assertThat(json).contains("CS2024001").contains("traces");
    }

    @Test
    void logistics_of_another_buyer_is_not_found() {
        McpAuthContext.set(new AuthenticatedUser("buyer_b", 2L, "CUSTOMER"));

        assertThatThrownBy(() -> logisticsTools.queryLogistics("CS2024001"))
                .isInstanceOf(NotFoundException.class);
    }

    @Test
    void buyer_can_apply_for_after_sales() throws Exception {
        McpAuthContext.set(new AuthenticatedUser("buyer_a", 1L, "CUSTOMER"));

        String json = afterSalesTools.createAfterSalesRequest("CS2024002", "REFUND", "尺码不合适");

        assertThat(json).contains("requestNo").contains("PENDING");
    }

    @Test
    void agent_cannot_create_after_sales() {
        McpAuthContext.set(new AuthenticatedUser("cs_agent", 4L, "CS_AGENT"));

        assertThatThrownBy(() -> afterSalesTools.createAfterSalesRequest("CS2024002", "REFUND", "代申请"))
                .isInstanceOf(ForbiddenOperationException.class);
    }

    @Test
    void invalid_after_sales_type_is_rejected() {
        McpAuthContext.set(new AuthenticatedUser("buyer_a", 1L, "CUSTOMER"));

        assertThatThrownBy(() -> afterSalesTools.createAfterSalesRequest("CS2024002", "FREE", "x"))
                .isInstanceOf(InvalidInputException.class);
    }

    @Test
    void buyer_only_lists_their_own_after_sales() throws Exception {
        McpAuthContext.set(new AuthenticatedUser("buyer_a", 1L, "CUSTOMER"));
        afterSalesTools.createAfterSalesRequest("CS2024001", "RETURN", "质量问题");

        String json = afterSalesTools.listAfterSales(null);

        assertThat(json).contains("CS2024001");
        assertThat(json).doesNotContain("CS2024005");
    }

    @Test
    void agent_lists_all_after_sales() throws Exception {
        McpAuthContext.set(new AuthenticatedUser("buyer_b", 2L, "CUSTOMER"));
        afterSalesTools.createAfterSalesRequest("CS2024005", "RETURN", "买家B的退货");

        McpAuthContext.set(new AuthenticatedUser("cs_agent", 4L, "CS_AGENT"));
        String json = afterSalesTools.listAfterSales("PENDING");

        assertThat(json).contains("CS2024005");
    }

    @Test
    void buyer_without_after_sales_gets_empty_list() throws Exception {
        McpAuthContext.set(new AuthenticatedUser("buyer_c", 3L, "CUSTOMER"));

        assertThat(afterSalesTools.listAfterSales(null)).isEqualTo("[]");
    }

    @Test
    void status_filter_excludes_other_statuses() throws Exception {
        McpAuthContext.set(new AuthenticatedUser("buyer_a", 1L, "CUSTOMER"));
        afterSalesTools.createAfterSalesRequest("CS2024003", "EXCHANGE", "换货");

        String json = afterSalesTools.listAfterSales("PENDING");

        assertThat(json).contains("PENDING").doesNotContain("APPROVED");
    }
}
