package com.example.csagent.api;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.domain.OrderEntity;
import com.example.csagent.store.OrderMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 订单查询走 MySQL（T02）。内存实现退役后，这里能通过就说明数据确实来自数据库。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class OrderQueryApiTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private OrderMapper orderMapper;

    private String tokenFor(String username) throws Exception {
        String body = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"" + username + "\",\"password\":\"demo123\"}"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return com.jayway.jsonpath.JsonPath.read(body, "$.token");
    }

    @Test
    void buyer_reads_order_details_from_the_database() throws Exception {
        String token = tokenFor("buyer_a");

        mockMvc.perform(get("/api/orders/CS2024001").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderNo").value("CS2024001"))
                .andExpect(jsonPath("$.item").value("轻量跑步鞋 42码"))
                .andExpect(jsonPath("$.amount").value(399.00))
                .andExpect(jsonPath("$.status").value("已签收"))
                .andExpect(jsonPath("$.createdAt").value("2026-10-20"));
    }

    @Test
    void unknown_order_returns_404_not_500() throws Exception {
        String token = tokenFor("buyer_a");

        mockMvc.perform(get("/api/orders/CS9999999").header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());
    }

    @Test
    void creating_a_refund_is_not_required_to_read_an_order() {
        // 保证测试库真的被 V2 种子灌过，而不是内存兜底
        Long count = orderMapper.selectCount(new LambdaQueryWrapper<>());
        assertThat(count).isEqualTo(12L);
        OrderEntity first = orderMapper.selectById("CS2024001");
        assertThat(first).isNotNull();
        assertThat(first.getUserId()).isEqualTo(1L);
    }
}
