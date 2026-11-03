package com.example.csagent.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 统一的错误响应信封：{@code {"error": "<CODE>", "message": "<可读说明>"}}。
 * 所有过滤器与控制器异常处理器都走这里，避免同类 JSON 手写多份。
 */
public final class ApiErrors {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private ApiErrors() {
    }

    public static void write(HttpServletResponse response, int status, String code, String message)
            throws IOException {
        response.setStatus(status);
        response.setContentType("application/json;charset=UTF-8");
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("error", code);
        body.put("message", message);
        MAPPER.writeValue(response.getWriter(), body);
    }
}
