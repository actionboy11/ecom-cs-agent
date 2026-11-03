package com.example.csagent.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * T05：坐席可读全部订单/物流并能查审计；买家无权访问审计接口。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AuditApiTest {

    @Autowired
    private MockMvc mockMvc;

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Test
    void buyer_may_not_read_the_audit_trail() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        mockMvc.perform(get("/api/audit").header("Authorization", "Bearer " + token))
                .andExpect(status().isForbidden());
    }

    @Test
    void agent_can_read_audit_records_including_denied_attempts() throws Exception {
        // 先制造一条越权记录（buyer_b 读 buyer_a 的订单）
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_b");
        mockMvc.perform(get("/api/orders/CS2024001").header("Authorization", "Bearer " + buyerToken))
                .andExpect(status().isNotFound());

        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");
        var body = mockMvc.perform(get("/api/audit").header("Authorization", "Bearer " + agentToken))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        var records = MAPPER.readTree(body);
        assertThat(records.size()).isGreaterThan(0);
        boolean hasDenied = false;
        for (var record : records) {
            if ("DENIED".equals(record.get("result").asText())
                    && "CS2024001".equals(record.get("resourceId").asText())) {
                hasDenied = true;
            }
        }
        assertThat(hasDenied).as("审计里应能看到 buyer_b 的越权尝试").isTrue();
    }

    @Test
    void agent_reads_another_buyers_order_and_is_audited_as_agent() throws Exception {
        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");

        mockMvc.perform(get("/api/orders/CS2024005").header("Authorization", "Bearer " + agentToken))
                .andExpect(status().isOk());

        var body = mockMvc.perform(get("/api/audit").header("Authorization", "Bearer " + agentToken))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        boolean auditedAsAgent = false;
        for (var record : MAPPER.readTree(body)) {
            if ("cs_agent".equals(record.get("actor").asText())
                    && "CS2024005".equals(record.get("resourceId").asText())
                    && "OK".equals(record.get("result").asText())) {
                auditedAsAgent = true;
            }
        }
        assertThat(auditedAsAgent).as("坐席查询也要留痕").isTrue();
    }

    @Test
    void agent_order_list_is_audited() throws Exception {
        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");
        mockMvc.perform(get("/api/orders").header("Authorization", "Bearer " + agentToken))
                .andExpect(status().isOk());

        var body = mockMvc.perform(get("/api/audit?limit=20").header("Authorization", "Bearer " + agentToken))
                .andReturn().getResponse().getContentAsString();
        boolean listedAudited = false;
        for (var record : MAPPER.readTree(body)) {
            if ("QUERY_ORDER_LIST".equals(record.get("action").asText())
                    && "cs_agent".equals(record.get("actor").asText())) {
                listedAudited = true;
            }
        }
        assertThat(listedAudited).as("坐席列举订单必须留痕").isTrue();
    }

    @Test
    void agent_logistics_query_is_audited() throws Exception {
        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");
        mockMvc.perform(get("/api/logistics/CS2024003").header("Authorization", "Bearer " + agentToken))
                .andExpect(status().isOk());

        var body = mockMvc.perform(get("/api/audit?limit=20").header("Authorization", "Bearer " + agentToken))
                .andReturn().getResponse().getContentAsString();
        boolean logisticsAudited = false;
        for (var record : MAPPER.readTree(body)) {
            if ("QUERY_LOGISTICS".equals(record.get("action").asText())
                    && "CS2024003".equals(record.get("resourceId").asText())
                    && "cs_agent".equals(record.get("actor").asText())) {
                logisticsAudited = true;
            }
        }
        assertThat(logisticsAudited).isTrue();
    }

    @Test
    void buyer_cannot_apply_after_sales_for_someone_elses_order() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_b");
        mockMvc.perform(post("/api/refunds")
                        .header("Authorization", "Bearer " + buyerToken)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content("{\"orderNo\":\"CS2024001\",\"reason\":\"test\"}"))
                .andExpect(status().isNotFound());
    }
}
