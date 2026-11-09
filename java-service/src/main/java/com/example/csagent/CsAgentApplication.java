package com.example.csagent;

import com.example.csagent.mcp.McpIo;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class CsAgentApplication {

    public static void main(String[] args) {
        boolean stdio = McpIo.stdioMode();
        if (stdio) {
            // 先把日志赶去 stderr，再启动：MCP 的 stdout 只能有协议消息
            McpIo.enable();
        }
        SpringApplication app = new SpringApplication(CsAgentApplication.class);
        if (stdio) {
            app.setWebApplicationType(WebApplicationType.NONE);
        }
        app.run(args);
    }
}
