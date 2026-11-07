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
 * 测试自建数据，不依赖种子里那条 PENDING 的状态。
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
    private static final String BUYER_B_ORDER = "CS2024005";

    private String json(String token, String url) throws Exception {
        return mockMvc.perform(get(url).header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
    }

    @Test
    void buyer_only_sees_their_own_after_sales() throws Exception {
        String buyerAToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String buyerBToken = LoginSupport.tokenFor(mockMvc, "buyer_b");
        String requestA = AfterSalesTestSupport.create(mockMvc, buyerAToken, "CS2024001", "REFUND");
        String requestB = AfterSalesTestSupport.create(mockMvc, buyerBToken, BUYER_B_ORDER, "RETURN");

        var rows = MAPPER.readTree(json(buyerAToken, "/api/after-sales"));
        assertThat(rows.size()).isGreaterThan(0);
        boolean containsA = false;
        for (var row : rows) {
            assertThat(BUYER_A_ORDERS).contains(row.get("orderNo").asText());
            if (requestA.equals(row.get("requestNo").asText())) {
                containsA = true;
            }
            assertThat(row.get("requestNo").asText()).isNotEqualTo(requestB);
        }
        assertThat(containsA).isTrue();
    }

    @Test
    void buyer_b_sees_their_own_and_not_buyer_as() throws Exception {
        String buyerAToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String buyerBToken = LoginSupport.tokenFor(mockMvc, "buyer_b");
        String requestA = AfterSalesTestSupport.create(mockMvc, buyerAToken, "CS2024002", "REFUND");
        String requestB = AfterSalesTestSupport.create(mockMvc, buyerBToken, BUYER_B_ORDER, "EXCHANGE");

        var rows = MAPPER.readTree(json(buyerBToken, "/api/after-sales"));
        boolean containsB = false;
        for (var row : rows) {
            assertThat(row.get("requestNo").asText()).isNotEqualTo(requestA);
            if (requestB.equals(row.get("requestNo").asText())) {
                containsB = true;
            }
        }
        assertThat(containsB).as("买家的正向控制：应能看到自己刚创建的那条").isTrue();
    }

    @Test
    void agent_sees_requests_from_multiple_buyers() throws Exception {
        String buyerAToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String buyerBToken = LoginSupport.tokenFor(mockMvc, "buyer_b");
        String requestA = AfterSalesTestSupport.create(mockMvc, buyerAToken, "CS2024003", "RETURN");
        String requestB = AfterSalesTestSupport.create(mockMvc, buyerBToken, BUYER_B_ORDER, "RETURN");

        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");
        var rows = MAPPER.readTree(json(agentToken, "/api/after-sales"));
        boolean hasA = false;
        boolean hasB = false;
        for (var row : rows) {
            String requestNo = row.get("requestNo").asText();
            hasA |= requestNo.equals(requestA);
            hasB |= requestNo.equals(requestB);
        }
        assertThat(hasA).isTrue();
        assertThat(hasB).isTrue();
    }

    @Test
    void status_pending_filter_returns_only_pending() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String requestNo = AfterSalesTestSupport.create(mockMvc, buyerToken, "CS2024001", "REFUND");
        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");

        var rows = MAPPER.readTree(json(agentToken, "/api/after-sales?status=PENDING"));
        assertThat(rows.size()).isGreaterThan(0);
        boolean containsRequest = false;
        for (var row : rows) {
            assertThat(row.get("status").asText()).isEqualTo("PENDING");
            containsRequest |= row.get("requestNo").asText().equals(requestNo);
        }
        assertThat(containsRequest).isTrue();
    }

    @Test
    void status_approved_filter_returns_only_approved() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String requestNo = AfterSalesTestSupport.create(mockMvc, buyerToken, "CS2024002", "REFUND");
        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");
        mockMvc.perform(post("/api/after-sales/" + requestNo + "/review")
                        .header("Authorization", "Bearer " + agentToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"approved\":true}"))
                .andExpect(status().isOk());

        var rows = MAPPER.readTree(json(agentToken, "/api/after-sales?status=APPROVED"));
        assertThat(rows.size()).isGreaterThan(0);
        for (var row : rows) {
            assertThat(row.get("status").asText()).isEqualTo("APPROVED");
        }
    }

    @Test
    void invalid_status_is_rejected_with_400() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        mockMvc.perform(get("/api/after-sales?status=bogus").header("Authorization", "Bearer " + buyerToken))
                .andExpect(status().isBadRequest());
    }

    @Test
    void anonymous_cannot_list() throws Exception {
        mockMvc.perform(get("/api/after-sales")).andExpect(status().isUnauthorized());
    }

    @Test
    void listing_is_audited_with_filter_and_count() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        mockMvc.perform(get("/api/after-sales?status=PENDING").header("Authorization", "Bearer " + buyerToken))
                .andExpect(status().isOk());

        List<AuditLogEntity> rows = auditLogMapper.selectList(new LambdaQueryWrapper<AuditLogEntity>()
                .eq(AuditLogEntity::getAction, AuditEvent.ACTION_QUERY_AFTER_SALES_LIST)
                .eq(AuditLogEntity::getActor, "buyer_a")
                .orderByDesc(AuditLogEntity::getId)
                .last("limit 1"));
        assertThat(rows).hasSize(1);
        assertThat(rows.get(0).getResult()).isEqualTo(AuditEvent.RESULT_OK);
        var detail = MAPPER.readTree(rows.get(0).getDetail());
        assertThat(detail.get("status").asText()).isEqualTo("PENDING");
        assertThat(detail.get("returned").isInt()).isTrue();
    }
}
