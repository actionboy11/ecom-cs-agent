package com.example.csagent.mcp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/** S5-1：MCP 协议层（不依赖 Spring 与数据库）。 */
class McpProtocolTest {

    private final ObjectMapper mapper = new ObjectMapper();
    private final McpProtocol protocol = new McpProtocol(List.of(
            new McpProtocol.ToolSpec("echo", "回显", Map.of("type", "object"), args -> "echo:" + args.get("text"))
    ), mapper);

    @Test
    void initialize_returns_protocol_and_server_info() throws Exception {
        JsonNode response = mapper.readTree(protocol.handle(
                "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}"));

        assertThat(response.path("result").path("protocolVersion").asText()).isEqualTo("2024-11-05");
        assertThat(response.path("result").path("serverInfo").path("name").asText())
                .isEqualTo("cs-agent-business");
    }

    @Test
    void tools_list_exposes_name_and_schema() throws Exception {
        JsonNode response = mapper.readTree(protocol.handle(
                "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\",\"params\":{}}"));

        JsonNode tool = response.path("result").path("tools").get(0);
        assertThat(tool.path("name").asText()).isEqualTo("echo");
        assertThat(tool.path("inputSchema").path("type").asText()).isEqualTo("object");
    }

    @Test
    void tools_call_returns_text_content() throws Exception {
        JsonNode response = mapper.readTree(protocol.handle(
                "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\","
                        + "\"params\":{\"name\":\"echo\",\"arguments\":{\"text\":\"hi\"}}}"));

        assertThat(response.path("result").path("content").get(0).path("text").asText())
                .isEqualTo("echo:hi");
    }

    @Test
    void unknown_tool_is_an_error_result() throws Exception {
        JsonNode response = mapper.readTree(protocol.handle(
                "{\"jsonrpc\":\"2.0\",\"id\":4,\"method\":\"tools/call\","
                        + "\"params\":{\"name\":\"nope\",\"arguments\":{}}}"));

        assertThat(response.path("result").path("isError").asBoolean()).isTrue();
    }

    @Test
    void notifications_are_not_answered() throws Exception {
        assertThat(protocol.handle("{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}")).isNull();
    }

    @Test
    void unknown_method_returns_jsonrpc_error() throws Exception {
        JsonNode response = mapper.readTree(protocol.handle(
                "{\"jsonrpc\":\"2.0\",\"id\":5,\"method\":\"nope\"}"));

        assertThat(response.path("error").path("code").asInt()).isEqualTo(-32601);
    }
}
