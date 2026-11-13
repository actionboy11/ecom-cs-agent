package com.example.csagent.api;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.domain.AuditLogEntity;
import com.example.csagent.store.AuditLogMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** S6-3：Agent 侧越权上报的内部审计接口。 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class InternalAuditTest {

    private static final String TOKEN = "test-internal-token";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AuditLogMapper auditLogMapper;

    private String body(String threadId) {
        return """
                {"actor":"buyer_b","actorRole":"CUSTOMER","action":"THREAD_ACCESS",
                 "resourceType":"THREAD","resourceId":"%s","result":"DENIED",
                 "path":"/api/v1/chat","detail":{"reason":"not_owner"}}
                """.formatted(threadId);
    }

    @Test
    void writes_denied_audit_with_valid_internal_token() throws Exception {
        mockMvc.perform(post("/api/internal/audit")
                        .header("X-Internal-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body("t-audit-1")))
                .andExpect(status().isOk());

        var rows = auditLogMapper.selectList(new LambdaQueryWrapper<AuditLogEntity>()
                .eq(AuditLogEntity::getAction, "THREAD_ACCESS")
                .eq(AuditLogEntity::getResourceId, "t-audit-1"));
        assertThat(rows).isNotEmpty();
        assertThat(rows.get(rows.size() - 1).getResult()).isEqualTo("DENIED");
        assertThat(rows.get(rows.size() - 1).getActor()).isEqualTo("buyer_b");
    }

    @Test
    void rejects_missing_or_wrong_token() throws Exception {
        mockMvc.perform(post("/api/internal/audit")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body("t-audit-2")))
                .andExpect(status().isUnauthorized());

        mockMvc.perform(post("/api/internal/audit")
                        .header("X-Internal-Token", "wrong")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body("t-audit-3")))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void rejects_forged_action() throws Exception {
        String forged = """
                {"actor":"x","actorRole":"CUSTOMER","action":"LOGIN","resourceType":"THREAD",
                 "resourceId":"t-forge","result":"OK","path":"/api/v1/chat","detail":{}}
                """;
        mockMvc.perform(post("/api/internal/audit")
                        .header("X-Internal-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(forged))
                .andExpect(status().isBadRequest());
    }

    @Test
    void rejects_non_business_path() throws Exception {
        String bad = body("t-path").replace("/api/v1/chat", "/evil");
        mockMvc.perform(post("/api/internal/audit")
                        .header("X-Internal-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(bad))
                .andExpect(status().isBadRequest());
    }

    @Test
    void long_actor_is_clipped_instead_of_lost() throws Exception {
        String longActor = "a".repeat(80);
        mockMvc.perform(post("/api/internal/audit")
                        .header("X-Internal-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body("t-long").replace("\"buyer_b\"", "\"" + longActor + "\"")))
                .andExpect(status().isOk());

        var rows = auditLogMapper.selectList(new LambdaQueryWrapper<AuditLogEntity>()
                .eq(AuditLogEntity::getAction, "THREAD_ACCESS")
                .eq(AuditLogEntity::getResourceId, "t-long"));
        assertThat(rows).isNotEmpty();
        assertThat(rows.get(rows.size() - 1).getActor()).hasSize(50);
    }
}
