package com.example.csagent.api;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** 未配置内部令牌时，接口必须 fail-closed。 */
@SpringBootTest(properties = "app.internal-audit-token=")
@AutoConfigureMockMvc
@ActiveProfiles("test")
class InternalAuditDisabledTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void blank_configuration_rejects_everything() throws Exception {
        mockMvc.perform(post("/api/internal/audit")
                        .header("X-Internal-Token", "")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"actor":"x","actorRole":"CUSTOMER","action":"THREAD_ACCESS",
                                 "resourceType":"THREAD","resourceId":"t","result":"DENIED",
                                 "path":"/api/v1/chat","detail":{"reason":"not_owner"}}
                                """))
                .andExpect(status().isUnauthorized());
    }
}
