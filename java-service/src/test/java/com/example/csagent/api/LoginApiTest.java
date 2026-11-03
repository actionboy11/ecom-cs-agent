package com.example.csagent.api;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.domain.UserEntity;
import com.example.csagent.store.UserMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 登录接口的 HTTP 层测试（切片 1 唯一的测试缝）。
 *
 * <p>数据库：连本地 compose 的 MySQL 测试库 {@code cs_agent_test}（profile=test）。
 * 原计划用 Testcontainers，但本机 Docker 29.4 的命名管道与 docker-java 握手返回 400，
 * 因此按预先约定的降级方案改为常驻测试库——仍然是真实 MySQL 语义，Flyway 迁移照常执行。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class LoginApiTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserMapper userMapper;

    @Autowired
    private com.example.csagent.security.JwtService jwtService;

    @Test
    void buyer_a_can_login_and_receives_a_token() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"buyer_a","password":"demo123"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token").isNotEmpty())
                .andExpect(jsonPath("$.role").value("CUSTOMER"))
                .andExpect(jsonPath("$.displayName").value("买家A"))
                .andExpect(jsonPath("$.userId").value(1));
    }

    @Test
    void wrong_password_and_unknown_user_are_indistinguishable() throws Exception {
        MvcResult wrongPassword = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"buyer_a","password":"not-the-password"}
                                """))
                .andExpect(status().isUnauthorized())
                .andReturn();

        MvcResult unknownUser = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"nobody","password":"demo123"}
                                """))
                .andExpect(status().isUnauthorized())
                .andReturn();

        assertThat(wrongPassword.getResponse().getContentAsString())
                .isEqualTo(unknownUser.getResponse().getContentAsString());
    }

    @Test
    void protected_endpoint_requires_a_token() throws Exception {
        mockMvc.perform(get("/api/orders/CS2024001"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error").value("UNAUTHORIZED"));
    }

    @Test
    void issued_token_unlocks_a_protected_endpoint() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        mockMvc.perform(get("/api/orders/CS2024001").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk());
    }

    @Test
    void issued_token_carries_identity_and_two_hour_ttl() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");
        var claims = jwtService.parse(token);

        assertThat(claims.getSubject()).isEqualTo("buyer_a");
        assertThat(claims.get("userId", Number.class).longValue()).isEqualTo(1L);
        assertThat(claims.get("role", String.class)).isEqualTo("CUSTOMER");
        long ttl = claims.getExpiration().toInstant().getEpochSecond()
                - claims.getIssuedAt().toInstant().getEpochSecond();
        assertThat(ttl).isBetween(7199L, 7201L);
    }

    @Test
    void all_four_seed_accounts_can_login() throws Exception {
        for (String username : new String[]{"buyer_a", "buyer_b", "buyer_c", "cs_agent"}) {
            mockMvc.perform(post("/api/auth/login")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("{\"username\":\"" + username + "\",\"password\":\"demo123\"}"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.token").isNotEmpty());
        }
    }

    @Test
    void seed_users_store_bcrypt_hashes_not_placeholders() {
        for (String username : new String[]{"buyer_a", "buyer_b", "buyer_c", "cs_agent"}) {
            UserEntity user = userMapper.selectOne(
                    new LambdaQueryWrapper<UserEntity>().eq(UserEntity::getUsername, username));
            assertThat(user).as("种子用户 %s 应存在", username).isNotNull();
            assertThat(user.getPasswordHash())
                    .as("%s 的密码必须是 BCrypt 哈希", username)
                    .startsWith("$2")
                    .doesNotContain("__PENDING__");
        }
    }
}
