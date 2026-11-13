package com.example.csagent.api;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.domain.AuditLogEntity;
import com.example.csagent.service.AuditEvent;
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

/** S6-3：登录审计（SPEC §7.3 的 LOGIN 约束）。 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AuthAuditTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AuditLogMapper auditLogMapper;

    private List<AuditLogEntity> loginRows(String actor) {
        return auditLogMapper.selectList(new LambdaQueryWrapper<AuditLogEntity>()
                .eq(AuditLogEntity::getAction, AuditEvent.ACTION_LOGIN)
                .eq(AuditLogEntity::getActor, actor));
    }

    @Test
    void successful_login_is_audited() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"buyer_a\",\"password\":\"demo123\"}"))
                .andExpect(status().isOk());

        List<AuditLogEntity> rows = loginRows("buyer_a");
        assertThat(rows).isNotEmpty();
        assertThat(rows.get(rows.size() - 1).getResult()).isEqualTo(AuditEvent.RESULT_OK);
        // 不记录密码
        assertThat(rows.get(rows.size() - 1).getDetail() == null
                || !rows.get(rows.size() - 1).getDetail().contains("demo123")).isTrue();
    }

    @Test
    void failed_login_is_audited_without_distinguishing_reason() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"buyer_a\",\"password\":\"wrong\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error").value("INVALID_CREDENTIALS"));

        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"no_such_user\",\"password\":\"wrong\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error").value("INVALID_CREDENTIALS"));

        List<AuditLogEntity> rows = loginRows("no_such_user");
        assertThat(rows).isNotEmpty();
        assertThat(rows.get(rows.size() - 1).getResult()).isEqualTo(AuditEvent.RESULT_DENIED);
        assertThat(rows.get(rows.size() - 1).getDetail()).contains("credentials");
    }
}
