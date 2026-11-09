package com.example.csagent.mcp;

import com.example.csagent.api.NotFoundException;
import com.example.csagent.security.AuthenticatedUser;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** S5-1：MCP 工具的身份与权限口径。 */
@SpringBootTest
@ActiveProfiles("test")
class OrderMcpToolsTest {

    @Autowired
    private OrderMcpTools tools;

    @AfterEach
    void clearContext() {
        McpAuthContext.clear();
    }

    @Test
    void returns_the_callers_own_order() throws Exception {
        McpAuthContext.set(new AuthenticatedUser("buyer_a", 1L, "CUSTOMER"));

        String json = tools.getOrder("CS2024001");

        assertThat(json).contains("\"orderNo\":\"CS2024001\"");
        assertThat(json).contains("\"item\"");
    }

    @Test
    void another_buyers_order_is_reported_as_not_found() {
        McpAuthContext.set(new AuthenticatedUser("buyer_b", 2L, "CUSTOMER"));

        assertThatThrownBy(() -> tools.getOrder("CS2024001"))
                .isInstanceOf(NotFoundException.class);
    }

    @Test
    void missing_order_no_is_a_missing_slot_not_not_found() {
        McpAuthContext.set(new AuthenticatedUser("buyer_a", 1L, "CUSTOMER"));

        assertThatThrownBy(() -> tools.getOrder(" "))
                .isInstanceOf(MissingSlotException.class)
                .hasMessageContaining("MISSING_SLOT");
    }

    @Test
    void tools_reject_calls_without_identity() {
        McpAuthContext.clear();

        assertThatThrownBy(() -> tools.getOrder("CS2024001"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("UNAUTHORIZED");
    }

    @Test
    void expired_identity_is_rejected() {
        McpAuthContext.set(new AuthenticatedUser("buyer_a", 1L, "CUSTOMER"), System.currentTimeMillis() - 1);

        assertThatThrownBy(() -> tools.getOrder("CS2024001"))
                .hasMessageContaining("令牌已过期");
    }

    @Test
    void agent_can_read_any_order() throws Exception {
        McpAuthContext.set(new AuthenticatedUser("cs_agent", 4L, "CS_AGENT"));

        assertThat(tools.getOrder("CS2024001")).contains("CS2024001");
    }
}
