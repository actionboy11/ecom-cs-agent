package com.example.csagent.api;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.domain.AuditLogEntity;
import com.example.csagent.service.AuditEvent;
import com.example.csagent.store.AuditLogMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * S2-3：售后列表。买家只看自己、坐席看全部、可按状态过滤、读取留痕。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AfterSalesListApiTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AuditLogMapper auditLogMapper;

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final Set<String> BUYER_A_ORDERS = Set.of("CS2024001", "CS2024002", "CS2024003", "CS2024004");

    private String createRequest(String token, String orderNo, String type) throws Exception {
        String body = mockMvc.perform(post("/api/after-sales")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"orderNo\":\"" + orderNo + "\",\"type\":\"" + type + "\",\"reason\":\"测试\"}"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return com.jayway.jsonpath.JsonPath.read(body, "$.requestNo");
    }

    @Test
    void buyer_only_sees_their_own_after_sales() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        var body = mockMvc.perform(get("/api/after-sales").header("Authorization", "Bearer " + buyerToken))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        var rows = MAPPER.readTree(body);
        assertThat(rows.size()).isGreaterThan(0);
        for (var row : rows) {
            assertThat(BUYER_A_ORDERS).contains(row.get("orderNo").asText());
        }
    }

    @Test
    void buyer_b_does_not_see_buyer_as_requests() throws Exception {
        String buyerBToken = LoginSupport.tokenFor(mockMvc, "buyer_b");
        var body = mockMvc.perform(get("/api/after-sales").header("Authorization", "Bearer " + buyerBToken))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        for (var row : MAPPER.readTree(body)) {
            assertThat(BUYER_A_ORDERS).doesNotContain(row.get("orderNo").asText());
        }
    }

    @Test
    void agent_sees_requests_from_multiple_buyers() throws Exception {
        createRequest(LoginSupport.tokenFor(mockMvc, "buyer_b"), "CS2024005", "RETURN");

        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");
        var body = mockMvc.perform(get("/api/after-sales").header("Authorization", "Bearer " + agentToken))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        boolean hasBuyerAOrder = false;
        boolean hasBuyerBOrder = false;
        for (var row : MAPPER.readTree(body)) {
            String orderNo = row.get("orderNo").asText();
            if (BUYER_A_ORDERS.contains(orderNo)) {
                hasBuyerAOrder = true;
            }
            if ("CS2024005".equals(orderNo)) {
                hasBuyerBOrder = true;
            }
        }
        assertThat(hasBuyerAOrder).isTrue();
        assertThat(hasBuyerBOrder).isTrue();
    }

    @Test
    void status_filter_returns_only_that_status() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String requestNo = createRequest(buyerToken, "CS2024002", "REFUND");

        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");
        mockMvc.perform(post("/api/after-sales/" + requestNo + "/review")
                        .header("Authorization", "Bearer " + agentToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"approved\":true}"))
                .andExpect(status().isOk());

        var body = mockMvc.perform(get("/api/after-sales").param("status", "APPROVED")
                        .header("Authorization", "Bearer " + agentToken))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        var rows = MAPPER.readTree(body);
        assertThat(rows.size()).isGreaterThan(0);
        for (var row : rows) {
            assertThat(row.get("status").asText()).isEqualTo("APPROVED");
        }
    }

    @Test
    void anonymous_cannot_list() throws Exception {
        mockMvc.perform(get("/api/after-sales")).andExpect(status().isUnauthorized());
    }

    @Test
    void listing_is_audited() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        mockMvc.perform(get("/api/after-sales").header("Authorization", "Bearer " + buyerToken))
                .andExpect(status().isOk());

        List<AuditLogEntity> rows = auditLogMapper.selectList(new LambdaQueryWrapper<AuditLogEntity>()
                .eq(AuditLogEntity::getAction, AuditEvent.ACTION_QUERY_AFTER_SALES_LIST)
                .eq(AuditLogEntity::getActor, "buyer_a")
                .orderByDesc(AuditLogEntity::getId)
                .last("limit 1"));
        assertThat(rows).hasSize(1);
        assertThat(rows.get(0).getResult()).isEqualTo(AuditEvent.RESULT_OK);
        assertThat(rows.get(0).getDetail()).contains("returned");
    }
}
