package com.example.csagent.mcp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 最小 MCP（Model Context Protocol）服务端：JSON-RPC 2.0，stdio 传输。
 *
 * <p>只实现 Agent 实际用到的子集：initialize / tools/list / tools/call / ping。
 * 与 Spring AI 解耦，协议行为可单测。
 */
public class McpProtocol {

    public static final String PROTOCOL_VERSION = "2024-11-05";

    @FunctionalInterface
    public interface ToolHandler {
        Object call(Map<String, Object> arguments) throws Exception;
    }

    public record ToolSpec(String name, String description, Map<String, Object> inputSchema, ToolHandler handler) {
    }

    private final List<ToolSpec> tools;
    private final ObjectMapper mapper;

    public McpProtocol(List<ToolSpec> tools, ObjectMapper mapper) {
        this.tools = tools;
        this.mapper = mapper;
    }

    /** @return 响应 JSON；通知类消息返回 null（按 MCP 约定不回包）。 */
    public String handle(String line) throws Exception {
        JsonNode request = mapper.readTree(line);
        String method = request.path("method").asText("");
        JsonNode id = request.get("id");

        if (id == null || id.isNull()) {
            return null; // notifications/initialized 等通知
        }

        ObjectNode response = mapper.createObjectNode();
        response.put("jsonrpc", "2.0");
        response.set("id", id);

        switch (method) {
            case "initialize" -> response.set("result", initializeResult());
            case "tools/list" -> response.set("result", toolsListResult());
            case "tools/call" -> response.set("result", toolsCallResult(request.path("params")));
            case "ping" -> response.set("result", mapper.createObjectNode());
            default -> response.set("error", error(-32601, "Method not found: " + method));
        }
        return mapper.writeValueAsString(response);
    }

    private ObjectNode initializeResult() {
        ObjectNode result = mapper.createObjectNode();
        result.put("protocolVersion", PROTOCOL_VERSION);
        ObjectNode capabilities = result.putObject("capabilities");
        capabilities.putObject("tools");
        ObjectNode serverInfo = result.putObject("serverInfo");
        serverInfo.put("name", "cs-agent-business");
        serverInfo.put("version", "0.1.0");
        return result;
    }

    private ObjectNode toolsListResult() {
        ObjectNode result = mapper.createObjectNode();
        ArrayNode array = result.putArray("tools");
        for (ToolSpec tool : tools) {
            ObjectNode node = array.addObject();
            node.put("name", tool.name());
            node.put("description", tool.description());
            node.set("inputSchema", mapper.valueToTree(tool.inputSchema()));
        }
        return result;
    }

    private ObjectNode toolsCallResult(JsonNode params) {
        String name = params.path("name").asText("");
        ToolSpec tool = tools.stream().filter(t -> t.name().equals(name)).findFirst().orElse(null);

        ObjectNode result = mapper.createObjectNode();
        ArrayNode content = result.putArray("content");

        if (tool == null) {
            result.put("isError", true);
            content.addObject().put("type", "text").put("text", "未知工具: " + name);
            return result;
        }

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> arguments = mapper.convertValue(
                    params.path("arguments"), LinkedHashMap.class);
            Object output = tool.handler().call(arguments);
            content.addObject().put("type", "text").put("text", String.valueOf(output));
        } catch (Exception exc) {
            result.put("isError", true);
            content.addObject().put("type", "text").put("text", exc.getMessage());
        }
        return result;
    }

    private ObjectNode error(int code, String message) {
        ObjectNode error = mapper.createObjectNode();
        error.put("code", code);
        error.put("message", message);
        return error;
    }
}
