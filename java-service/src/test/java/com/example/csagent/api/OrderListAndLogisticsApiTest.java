package com.example.csagent.api;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.domain.AuditLogEntity;
import com.example.csagent.domain.LogisticsTraceEntity;
import com.example.csagent.service.AuditEvent;
import com.example.csagent.store.AuditLogMapper;
import com.example.csagent.store.LogisticsTraceMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * T04：订单列表只回自己的、物流做归属校验、商品保持公开。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class OrderListAndLogisticsApiTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AuditLogMapper auditLogMapper;

    @Autowired
    private LogisticsTraceMapper traceMapper;

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Test
    void buyer_list_contains_only_their_own_orders() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");

        MvcResult result = mockMvc.perform(get("/api/orders").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andReturn();

        var orders = MAPPER.readTree(result.getResponse().getContentAsString());
        assertThat(orders.size()).isEqualTo(4);
        for (var order : orders) {
            assertThat(order.get("orderNo").asText()).isIn(
                    "CS2024001", "CS2024002", "CS2024003", "CS2024004");
        }
    }

    @Test
    void agent_list_contains_every_order() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "cs_agent");
        mockMvc.perform(get("/api/orders").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(12));
    }

    @Test
    void buyer_cannot_read_another_buyers_logistics() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_b");

        MvcResult otherBuyersParcel = mockMvc.perform(get("/api/logistics/CS2024001")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound())
                .andReturn();

        MvcResult missingParcel = mockMvc.perform(get("/api/logistics/CS9999999")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound())
                .andReturn();

        assertThat(otherBuyersParcel.getResponse().getContentAsString())
                .isEqualTo(missingParcel.getResponse().getContentAsString());
    }

    @Test
    void logistics_denial_is_audited_as_a_logistics_resource() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_b");

        mockMvc.perform(get("/api/logistics/CS2024001").header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());

        AuditLogEntity latest = latestDenied("CS2024001");
        assertThat(latest.getActor()).isEqualTo("buyer_b");
        assertThat(latest.getAction()).isEqualTo(AuditEvent.ACTION_QUERY_LOGISTICS);
        assertThat(latest.getResourceType()).isEqualTo(AuditEvent.TYPE_LOGISTICS);
        assertThat(latest.getDetail()).contains("/api/logistics/CS2024001");
    }

    @Test
    void buyer_reads_own_logistics_with_traces_in_time_order() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");

        mockMvc.perform(get("/api/logistics/CS2024001").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.trackingNo").value("SF1234567890"))
                .andExpect(jsonPath("$.traces.length()").value(3))
                .andExpect(jsonPath("$.traces[0]").value(org.hamcrest.Matchers.containsString("2026-10-21")))
                .andExpect(jsonPath("$.traces[2]").value(org.hamcrest.Matchers.containsString("2026-10-23")));
    }

    @Test
    void traces_are_ordered_by_time_not_by_sequence_number() throws Exception {
        String token = LoginSupport.tokenFor(mockMvc, "buyer_a");

        // 造一条「seq 最大但时间最早」的轨迹：按 seq 排序会排到最后，按时间排序应排到最前
        LogisticsTraceEntity injected = new LogisticsTraceEntity();
        injected.setOrderNo("CS2024003");
        injected.setSeq(99);
        injected.setTraceTime(LocalDateTime.of(2026, 10, 1, 8, 0));
        injected.setContent("TEST-最早节点");
        traceMapper.insert(injected);

        try {
            mockMvc.perform(get("/api/logistics/CS2024003").header("Authorization", "Bearer " + token))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.traces[0]")
                            .value(org.hamcrest.Matchers.containsString("2026-10-01")));
        } finally {
            traceMapper.deleteById(injected.getId());
        }
    }

    @Test
    void product_search_is_public() throws Exception {
        mockMvc.perform(get("/api/products/search").param("keyword", "耳机"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].sku").value("SKU1002"));
    }

    private AuditLogEntity latestDenied(String resourceId) {
        var rows = auditLogMapper.selectList(new LambdaQueryWrapper<AuditLogEntity>()
                .eq(AuditLogEntity::getResult, AuditEvent.RESULT_DENIED)
                .eq(AuditLogEntity::getResourceId, resourceId)
                .orderByDesc(AuditLogEntity::getId)
                .last("limit 1"));
        assertThat(rows).isNotEmpty();
        return rows.get(0);
    }
}
