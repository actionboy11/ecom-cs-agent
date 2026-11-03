package com.example.csagent.api;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.domain.AuditLogEntity;
import com.example.csagent.service.AuditEvent;
import com.example.csagent.store.AuditLogMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 越权拦截（T03）：查他人订单必须与「订单不存在」不可区分。
 * 断言外部行为（状态码 + 响应体），审计在 /api/audit 改读数据库（T05）之前用 Mapper 核对。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class OrderOwnershipApiTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AuditLogMapper auditLogMapper;

    @Test
    void reading_another_buyers_order_looks_exactly_like_a_missing_order() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_b");

        MvcResult otherBuyersOrder = mockMvc.perform(get("/api/orders/CS2024001")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound())
                .andReturn();

        MvcResult missingOrder = mockMvc.perform(get("/api/orders/CS9999999")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound())
                .andReturn();

        assertThat(otherBuyersOrder.getResponse().getContentAsString())
                .isEqualTo(missingOrder.getResponse().getContentAsString());
    }

    @Test
    void denied_access_is_audited_with_request_path_and_no_conversation_text() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_b");
        long before = countDenied("CS2024002");

        mockMvc.perform(get("/api/orders/CS2024002").header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());

        // 测试库跨运行保留数据，因此断言「本次新增恰好一条」而不是总数
        assertThat(countDenied("CS2024002")).isEqualTo(before + 1);

        AuditLogEntity entry = latestDenied("CS2024002");
        assertThat(entry.getActor()).isEqualTo("buyer_b");
        assertThat(entry.getActorRole()).isEqualTo("CUSTOMER");
        assertThat(entry.getAction()).isEqualTo(AuditEvent.ACTION_QUERY_ORDER);
        assertThat(entry.getResourceType()).isEqualTo(AuditEvent.TYPE_ORDER);
        assertThat(entry.getResult()).isEqualTo(AuditEvent.RESULT_DENIED);
        // detail 只放请求元数据：有 path，且没有别的字段（对话正文无处可藏）
        var detail = new com.fasterxml.jackson.databind.ObjectMapper().readTree(entry.getDetail());
        assertThat(detail.size()).isEqualTo(1);
        assertThat(detail.get("path").asText()).isEqualTo("/api/orders/CS2024002");
    }

    @Test
    void agent_may_read_any_order() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "cs_agent");
        mockMvc.perform(get("/api/orders/CS2024001").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk());
    }

    private long countDenied(String resourceId) {
        return auditLogMapper.selectCount(new LambdaQueryWrapper<AuditLogEntity>()
                .eq(AuditLogEntity::getResult, AuditEvent.RESULT_DENIED)
                .eq(AuditLogEntity::getResourceId, resourceId));
    }

    private AuditLogEntity latestDenied(String resourceId) {
        List<AuditLogEntity> rows = auditLogMapper.selectList(new LambdaQueryWrapper<AuditLogEntity>()
                .eq(AuditLogEntity::getResult, AuditEvent.RESULT_DENIED)
                .eq(AuditLogEntity::getResourceId, resourceId)
                .orderByDesc(AuditLogEntity::getId)
                .last("limit 1"));
        assertThat(rows).isNotEmpty();
        return rows.get(0);
    }
}
