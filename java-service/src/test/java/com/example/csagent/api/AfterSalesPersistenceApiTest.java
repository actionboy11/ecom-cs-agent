package com.example.csagent.api;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.domain.AfterSalesRequestEntity;
import com.example.csagent.domain.AuditLogEntity;
import com.example.csagent.service.AuditEvent;
import com.example.csagent.store.AfterSalesRequestMapper;
import com.example.csagent.store.AuditLogMapper;
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
 * S2-1 的持久化能力（路径已在 S2-2 改为 /api/after-sales）：
 * 落库字段、种子待审记录、越权拦截、审计留痕。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AfterSalesPersistenceApiTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AfterSalesRequestMapper afterSalesMapper;

    @Autowired
    private AuditLogMapper auditLogMapper;

    @Test
    void after_sales_is_persisted_with_type_status_and_owner() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");

        String body = mockMvc.perform(post("/api/after-sales")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"orderNo\":\"CS2024001\",\"type\":\"REFUND\",\"reason\":\"尺码不合适\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requestNo").isNotEmpty())
                .andExpect(jsonPath("$.status").value("PENDING"))
                .andReturn().getResponse().getContentAsString();

        String requestNo = com.jayway.jsonpath.JsonPath.read(body, "$.requestNo");

        AfterSalesRequestEntity saved = afterSalesMapper.selectById(requestNo);
        assertThat(saved).isNotNull();
        assertThat(saved.getOrderNo()).isEqualTo("CS2024001");
        assertThat(saved.getUserId()).isEqualTo(1L);
        assertThat(saved.getType()).isEqualTo("REFUND");
        assertThat(saved.getStatus()).isEqualTo("PENDING");
        assertThat(saved.getCreatedAt()).isNotNull();
    }

    @Test
    void seed_contains_one_pending_request_for_the_desk_to_review() {
        AfterSalesRequestEntity seed = afterSalesMapper.selectById("AS20261101000001");
        assertThat(seed).isNotNull();
        assertThat(seed.getOrderNo()).isEqualTo("CS2024003");
        assertThat(seed.getUserId()).isEqualTo(1L);
        assertThat(seed.getType()).isEqualTo("REFUND");
        assertThat(seed.getStatus()).isEqualTo("PENDING");
    }

    @Test
    void after_sales_creation_is_audited() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        String body = mockMvc.perform(post("/api/after-sales")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"orderNo\":\"CS2024002\",\"type\":\"REFUND\",\"reason\":\"不想要了\"}"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        String requestNo = com.jayway.jsonpath.JsonPath.read(body, "$.requestNo");

        List<AuditLogEntity> rows = auditLogMapper.selectList(new LambdaQueryWrapper<AuditLogEntity>()
                .eq(AuditLogEntity::getAction, AuditEvent.ACTION_APPLY_AFTER_SALES)
                .eq(AuditLogEntity::getResourceId, requestNo));
        assertThat(rows).hasSize(1);
        assertThat(rows.get(0).getActor()).isEqualTo("buyer_a");
        assertThat(rows.get(0).getResult()).isEqualTo(AuditEvent.RESULT_OK);
        assertThat(rows.get(0).getDetail()).contains("CS2024002");
    }

    @Test
    void buyer_cannot_apply_for_another_buyers_order() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_b");
        mockMvc.perform(post("/api/after-sales")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"orderNo\":\"CS2024001\",\"type\":\"REFUND\",\"reason\":\"test\"}"))
                .andExpect(status().isNotFound());
    }

    @Test
    void agent_may_not_create_after_sales() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "cs_agent");
        mockMvc.perform(post("/api/after-sales")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"orderNo\":\"CS2024001\",\"type\":\"REFUND\",\"reason\":\"坐席代申请\"}"))
                .andExpect(status().isForbidden());
    }
}
