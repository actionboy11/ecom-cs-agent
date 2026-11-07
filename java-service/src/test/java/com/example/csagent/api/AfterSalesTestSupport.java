package com.example.csagent.api;

import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 售后测试辅助：走真实接口创建售后申请并取回 requestNo，避免每个测试类各写一份。
 */
final class AfterSalesTestSupport {

    private AfterSalesTestSupport() {
    }

    static String create(MockMvc mockMvc, String token, String orderNo, String type, String reason)
            throws Exception {
        String body = mockMvc.perform(post("/api/after-sales")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"orderNo\":\"" + orderNo + "\",\"type\":\"" + type
                                + "\",\"reason\":\"" + reason + "\"}"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return com.jayway.jsonpath.JsonPath.read(body, "$.requestNo");
    }

    static String create(MockMvc mockMvc, String token, String orderNo, String type) throws Exception {
        return create(mockMvc, token, orderNo, type, "测试原因");
    }
}
