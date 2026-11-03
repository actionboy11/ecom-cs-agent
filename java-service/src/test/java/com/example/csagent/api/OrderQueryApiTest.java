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

    @Test
    void buyer_reads_order_details_from_the_database() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");

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
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");

        mockMvc.perform(get("/api/orders/CS9999999").header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());
    }

    @Test
    void public_product_endpoint_stays_open_without_a_token() throws Exception {
        mockMvc.perform(get("/api/products/SKU1002"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sku").value("SKU1002"));
    }

    @Test
    void seed_migration_loads_twelve_orders() {
        // 这条断言的是迁移脚本本身（V2 种子），不是接口行为；接口行为由上面的 HTTP 用例覆盖
        Long count = orderMapper.selectCount(new LambdaQueryWrapper<>());
        assertThat(count).isEqualTo(12L);
        OrderEntity first = orderMapper.selectById("CS2024001");
        assertThat(first).isNotNull();
        assertThat(first.getUserId()).isEqualTo(1L);
    }
}
