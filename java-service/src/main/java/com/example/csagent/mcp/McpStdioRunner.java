package com.example.csagent.mcp;

import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.security.JwtService;
import io.jsonwebtoken.Claims;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

/**
 * MCP stdio 服务端：由客户端以子进程方式启动（附加传输，HTTP `/mcp` 为主）。
 *
 * <p>身份在**进程启动时**由 `MCP_USER_TOKEN` 注入并校验；
 * 之后所有工具调用都使用这个身份，模型没有任何参数能改它。
 */
@Component
public class McpStdioRunner implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(McpStdioRunner.class);

    private final JwtService jwtService;
    private final McpToolRegistry registry;

    public McpStdioRunner(JwtService jwtService, McpToolRegistry registry) {
        this.jwtService = jwtService;
        this.registry = registry;
    }

    @Override
    public void run(String... args) throws Exception {
        if (!McpIo.stdioMode()) {
            return;
        }
        Claims claims = requireClaims(System.getenv("MCP_USER_TOKEN"));
        AuthenticatedUser user = new AuthenticatedUser(
                claims.getSubject(),
                ((Number) claims.get("userId")).longValue(),
                String.valueOf(claims.get("role")));
        McpAuthContext.set(user, claims.getExpiration().getTime());

        McpProtocol protocol = registry.protocol();
        log.info("MCP stdio 已就绪（identity={}）", user.username());

        BufferedReader stdin = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        try {
            String line;
            while ((line = stdin.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }
                McpProtocol.McpResponse response;
                try {
                    response = protocol.handle(line);
                } catch (RuntimeException exc) {
                    // 单行协议错误不能拖垮整个会话
                    response = new McpProtocol.McpResponse(400,
                            "{\"jsonrpc\":\"2.0\",\"id\":null,\"error\":{\"code\":-32700,\"message\":\"Parse error\"}}");
                }
                if (response.body() != null) {
                    McpIo.protocol().println(response.body());
                    McpIo.protocol().flush();
                }
            }
        } finally {
            McpAuthContext.clear();
        }
    }

    private Claims requireClaims(String token) {
        if (token == null || token.isBlank()) {
            throw new IllegalStateException("MCP stdio 需要 MCP_USER_TOKEN（登录用户的 JWT）");
        }
        return jwtService.parse(token);
    }
}
