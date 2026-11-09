package com.example.csagent.mcp;

import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.security.JwtService;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.jsonwebtoken.Claims;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

/**
 * MCP stdio 服务端：由 Python 客户端以子进程方式启动。
 *
 * <p>身份在**进程启动时**由 `MCP_USER_TOKEN` 注入并校验一次，
 * 之后所有工具调用都使用这个身份——模型没有任何参数能改它。
 */
@Component
public class McpStdioRunner implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(McpStdioRunner.class);

    private final JwtService jwtService;
    private final ObjectMapper objectMapper;
    private final OrderMcpTools orderMcpTools;

    public McpStdioRunner(JwtService jwtService, ObjectMapper objectMapper, OrderMcpTools orderMcpTools) {
        this.jwtService = jwtService;
        this.objectMapper = objectMapper;
        this.orderMcpTools = orderMcpTools;
    }

    @Override
    public void run(String... args) throws Exception {
        if (!McpIo.stdioMode()) {
            return;
        }
        McpAuthContext.set(requireUser(System.getenv("MCP_USER_TOKEN")));

        McpProtocol protocol = new McpProtocol(List.of(
                new McpProtocol.ToolSpec(
                        OrderMcpTools.NAME,
                        "查询订单详情；只能查当前登录用户自己的订单，他人订单返回不存在",
                        OrderMcpTools.schema(),
                        arguments -> orderMcpTools.getOrder(String.valueOf(arguments.get("orderNo"))))
        ), objectMapper);

        log.info("MCP stdio 已就绪（identity={}）", McpAuthContext.require().username());

        BufferedReader stdin = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String line;
        while ((line = stdin.readLine()) != null) {
            if (line.isBlank()) {
                continue;
            }
            String response = protocol.handle(line);
            if (response != null) {
                McpIo.protocol().println(response);
                McpIo.protocol().flush();
            }
        }
    }

    private AuthenticatedUser requireUser(String token) {
        if (token == null || token.isBlank()) {
            throw new IllegalStateException("MCP stdio 需要 MCP_USER_TOKEN（登录用户的 JWT）");
        }
        Claims claims = jwtService.parse(token);
        return new AuthenticatedUser(
                claims.getSubject(),
                ((Number) claims.get("userId")).longValue(),
                String.valueOf(claims.get("role")));
    }
}
