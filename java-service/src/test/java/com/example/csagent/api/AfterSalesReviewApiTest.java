package com.example.csagent.api;

import com.example.csagent.domain.AfterSalesRequestEntity;
import com.example.csagent.domain.AuditLogEntity;
import com.example.csagent.service.AuditEvent;
import com.example.csagent.store.AfterSalesRequestMapper;
import com.example.csagent.store.AuditLogMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * S2-2：三类售后 + 坐席审批 + 路径与命名对齐 SPEC。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AfterSalesReviewApiTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AfterSalesRequestMapper afterSalesMapper;

    @Autowired
    private AuditLogMapper auditLogMapper;

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private String createRequest(String token, String orderNo, String type) throws Exception {
        String body = mockMvc.perform(post("/api/after-sales")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"orderNo\":\"" + orderNo + "\",\"type\":\"" + type
                                + "\",\"reason\":\"测试原因\"}"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return com.jayway.jsonpath.JsonPath.read(body, "$.requestNo");
    }

    @Test
    void buyer_creates_an_exchange_request() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String requestNo = createRequest(token, "CS2024002", "EXCHANGE");

        AfterSalesRequestEntity saved = afterSalesMapper.selectById(requestNo);
        assertThat(saved).isNotNull();
        assertThat(saved.getType()).isEqualTo("EXCHANGE");
        assertThat(saved.getStatus()).isEqualTo("PENDING");
        assertThat(saved.getUserId()).isEqualTo(1L);
    }

    @Test
    void unknown_type_is_rejected() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        mockMvc.perform(post("/api/after-sales")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"orderNo\":\"CS2024001\",\"type\":\"FOO\",\"reason\":\"x\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void agent_approves_a_pending_request() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String requestNo = createRequest(buyerToken, "CS2024003", "RETURN");

        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");
        mockMvc.perform(post("/api/after-sales/" + requestNo + "/review")
                        .header("Authorization", "Bearer " + agentToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"approved\":true,\"note\":\"同意\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("APPROVED"))
                .andExpect(jsonPath("$.reviewedBy").value("cs_agent"));

        AfterSalesRequestEntity saved = afterSalesMapper.selectById(requestNo);
        assertThat(saved.getStatus()).isEqualTo("APPROVED");
        assertThat(saved.getReviewedBy()).isEqualTo("cs_agent");
        assertThat(saved.getReviewedAt()).isNotNull();
        assertThat(saved.getReviewNote()).isEqualTo("同意");
    }

    @Test
    void buyer_cannot_review() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String requestNo = createRequest(buyerToken, "CS2024001", "REFUND");

        mockMvc.perform(post("/api/after-sales/" + requestNo + "/review")
                        .header("Authorization", "Bearer " + buyerToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"approved\":true}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error").value("FORBIDDEN"));
    }

    @Test
    void agent_rejection_sets_rejected_and_is_audited() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String requestNo = createRequest(buyerToken, "CS2024001", "REFUND");

        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");
        mockMvc.perform(post("/api/after-sales/" + requestNo + "/review")
                        .header("Authorization", "Bearer " + agentToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"approved\":false,\"note\":\"不符合无理由条件\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("REJECTED"))
                .andExpect(jsonPath("$.reviewNote").value("不符合无理由条件"));

        AfterSalesRequestEntity saved = afterSalesMapper.selectById(requestNo);
        assertThat(saved.getStatus()).isEqualTo("REJECTED");
        assertThat(saved.getReviewedBy()).isEqualTo("cs_agent");

        List<AuditLogEntity> audit = auditLogMapper.selectList(new LambdaQueryWrapper<AuditLogEntity>()
                .eq(AuditLogEntity::getAction, AuditEvent.ACTION_REVIEW_AFTER_SALES)
                .eq(AuditLogEntity::getResourceId, requestNo));
        assertThat(audit).hasSize(1);
        assertThat(audit.get(0).getActor()).isEqualTo("cs_agent");
        assertThat(audit.get(0).getActorRole()).isEqualTo("CS_AGENT");
        assertThat(audit.get(0).getResult()).isEqualTo(AuditEvent.RESULT_OK);
        var detail = MAPPER.readTree(audit.get(0).getDetail());
        assertThat(detail.get("approved").asBoolean()).isFalse();
        assertThat(detail.get("status").asText()).isEqualTo("REJECTED");
    }

    @Test
    void an_already_reviewed_request_cannot_be_reviewed_again() throws Exception {
        String buyerToken = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String requestNo = createRequest(buyerToken, "CS2024002", "REFUND");
        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");

        mockMvc.perform(post("/api/after-sales/" + requestNo + "/review")
                        .header("Authorization", "Bearer " + agentToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"approved\":true}"))
                .andExpect(status().isOk());

        int second = mockMvc.perform(post("/api/after-sales/" + requestNo + "/review")
                        .header("Authorization", "Bearer " + agentToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"approved\":false}"))
                .andReturn().getResponse().getStatus();

        assertThat(second).isBetween(400, 499);
        assertThat(afterSalesMapper.selectById(requestNo).getStatus()).isEqualTo("APPROVED");
    }

    @Test
    void reviewing_an_unknown_request_returns_404() throws Exception {
        String agentToken = LoginSupport.tokenFor(mockMvc, "cs_agent");
        mockMvc.perform(post("/api/after-sales/AS00000000000000/review")
                        .header("Authorization", "Bearer " + agentToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"approved\":true}"))
                .andExpect(status().isNotFound());
    }
}
