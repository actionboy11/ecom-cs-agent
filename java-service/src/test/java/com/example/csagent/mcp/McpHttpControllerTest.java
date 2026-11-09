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
