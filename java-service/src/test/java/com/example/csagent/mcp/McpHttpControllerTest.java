package com.example.csagent.mcp;

import com.example.csagent.api.LoginSupport;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * S5-1：HTTP MCP 端点（`POST /mcp`）的行为。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class McpHttpControllerTest {

    @Autowired
    private MockMvc mockMvc;

    private String call(String body, String token) throws Exception {
        var request = post("/mcp").contentType(MediaType.APPLICATION_JSON).content(body);
        if (token != null) {
            request = request.header("Authorization", "Bearer " + token);
        }
        return mockMvc.perform(request)
                .andReturn().getResponse().getContentAsString();
    }

    @Test
    void initialize_via_post_mcp() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        mockMvc.perform(post("/mcp")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.result.protocolVersion").value("2024-11-05"))
                .andExpect(jsonPath("$.result.serverInfo.name").value("cs-agent-business"));
    }

    @Test
    void tools_list_via_post_mcp() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        mockMvc.perform(post("/mcp")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\",\"params\":{}}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.result.tools[0].name").value("get_order"))
                .andExpect(jsonPath("$.result.tools[0].inputSchema.required[0]").value("orderNo"));
    }

    @Test
    void tools_call_returns_own_order() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String body = call("{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\","
                + "\"params\":{\"name\":\"get_order\",\"arguments\":{\"orderNo\":\"CS2024001\"}}}", token);

        assertThat(body).contains("CS2024001").doesNotContain("isError");
    }

    @Test
    void tools_call_other_buyers_order_is_404() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_b");
        mockMvc.perform(post("/mcp")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"jsonrpc\":\"2.0\",\"id\":4,\"method\":\"tools/call\","
                                + "\"params\":{\"name\":\"get_order\",\"arguments\":{\"orderNo\":\"CS2024001\"}}}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value(-32004));
    }

    @Test
    void tools_list_exposes_all_four_tools() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String body = call("{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"tools/list\",\"params\":{}}", token);

        assertThat(body)
                .contains("get_order")
                .contains("get_logistics")
                .contains("apply_after_sales")
                .contains("list_after_sales");
    }

    @Test
    void logistics_call_via_mcp() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String body = call("{\"jsonrpc\":\"2.0\",\"id\":8,\"method\":\"tools/call\","
                + "\"params\":{\"name\":\"get_logistics\",\"arguments\":{\"orderNo\":\"CS2024001\"}}}", token);

        assertThat(body).contains("CS2024001");
    }

    @Test
    void agent_cannot_apply_after_sales_via_mcp() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "cs_agent");
        mockMvc.perform(post("/mcp")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"jsonrpc\":\"2.0\",\"id\":9,\"method\":\"tools/call\","
                                + "\"params\":{\"name\":\"apply_after_sales\","
                                + "\"arguments\":{\"orderNo\":\"CS2024001\",\"type\":\"REFUND\",\"reason\":\"x\"}}}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error.code").value(-32003));
    }

    @Test
    void buyer_can_create_after_sales_via_mcp() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String body = call("{\"jsonrpc\":\"2.0\",\"id\":10,\"method\":\"tools/call\","
                + "\"params\":{\"name\":\"apply_after_sales\","
                + "\"arguments\":{\"orderNo\":\"CS2024002\",\"type\":\"REFUND\",\"reason\":\"尺码不合适\"}}}", token);

        // 工具结果是一段文本，内部才是 JSON，因此按子串断言
        assertThat(body).contains("PENDING").contains("reviewedBy");
    }

    @Test
    void logistics_of_another_buyer_is_404_via_mcp() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_b");
        mockMvc.perform(post("/mcp")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"jsonrpc\":\"2.0\",\"id\":11,\"method\":\"tools/call\","
                                + "\"params\":{\"name\":\"get_logistics\",\"arguments\":{\"orderNo\":\"CS2024001\"}}}"))
                .andExpect(status().isNotFound());
    }

    @Test
    void buyer_without_after_sales_gets_empty_array() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_c");
        String body = call("{\"jsonrpc\":\"2.0\",\"id\":12,\"method\":\"tools/call\","
                + "\"params\":{\"name\":\"list_after_sales\",\"arguments\":{}}}", token);

        assertThat(body).contains("[]");
    }

    @Test
    void missing_token_is_401() throws Exception {
        mockMvc.perform(post("/mcp")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"jsonrpc\":\"2.0\",\"id\":5,\"method\":\"initialize\",\"params\":{}}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void malformed_json_is_parse_error() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        mockMvc.perform(post("/mcp")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{oops"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value(-32700));
    }

    @Test
    void missing_order_no_is_missing_slot() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        mockMvc.perform(post("/mcp")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"jsonrpc\":\"2.0\",\"id\":6,\"method\":\"tools/call\","
                                + "\"params\":{\"name\":\"get_order\",\"arguments\":{}}}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value(-32001));
    }
}
