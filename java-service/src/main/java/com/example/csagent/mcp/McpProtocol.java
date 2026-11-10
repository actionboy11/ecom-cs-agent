package com.example.csagent.mcp;

import com.example.csagent.api.NotFoundException;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 最小 MCP（Model Context Protocol）服务端：JSON-RPC 2.0。
 *
 * <p>只实现 Agent 实际用到的子集：initialize / tools/list / tools/call / ping。
 * 与传输解耦：HTTP `/mcp` 与 stdio 共用这一份实现。
 */
public class McpProtocol {

    public static final String PROTOCOL_VERSION = "2024-11-05";

    @FunctionalInterface
    public interface ToolHandler {
        Object call(Map<String, Object> arguments) throws Exception;
    }

    public record ToolSpec(String name, String description, Map<String, Object> inputSchema, ToolHandler handler) {
    }

    /** HTTP 状态 + 响应体（stdio 只用 body）。 */
    public record McpResponse(int status, String body) {
    }

    private final List<ToolSpec> tools;
    private final ObjectMapper mapper;

    public McpProtocol(List<ToolSpec> tools, ObjectMapper mapper) {
        this.tools = tools;
        this.mapper = mapper;
    }

    public McpResponse handle(String line) {
        JsonNode request;
        try {
            request = mapper.readTree(line);
        } catch (JsonProcessingException exc) {
            return new McpResponse(400, errorResponse(null, -32700, "Parse error"));
        }
        if (request == null || !request.isObject()) {
            return new McpResponse(400, errorResponse(null, -32600, "Invalid Request"));
        }

        String method = request.path("method").asText("");
        JsonNode id = request.get("id");
        if (id == null || id.isNull()) {
            return new McpResponse(202, null); // 通知不回包
        }

        return switch (method) {
            case "initialize" -> new McpResponse(200, okResponse(id, initializeResult()));
            case "tools/list" -> new McpResponse(200, okResponse(id, toolsListResult()));
            case "ping" -> new McpResponse(200, okResponse(id, mapper.createObjectNode()));
            case "tools/call" -> toolsCall(id, request.path("params"));
            default -> new McpResponse(200, errorResponse(id, -32601, "Method not found: " + method));
        };
    }

    private McpResponse toolsCall(JsonNode id, JsonNode params) {
        String name = params.path("name").asText("");
        ToolSpec tool = tools.stream().filter(t -> t.name().equals(name)).findFirst().orElse(null);
        if (tool == null) {
            return new McpResponse(400, errorResponse(id, -32602, "Unknown tool: " + name));
        }

        try {
            JsonNode argumentsNode = params.get("arguments");
            @SuppressWarnings("unchecked")
            Map<String, Object> arguments = (argumentsNode == null || argumentsNode.isNull())
                    ? new LinkedHashMap<>()
                    : mapper.convertValue(argumentsNode, LinkedHashMap.class);
            Object output = tool.handler().call(arguments);
            return new McpResponse(200, okResponse(id, toolResult(String.valueOf(output), false)));
        } catch (MissingSlotException exc) {
            return new McpResponse(400, errorResponse(id, -32001, exc.getMessage()));
        } catch (com.example.csagent.service.ForbiddenOperationException exc) {
            return new McpResponse(403, errorResponse(id, -32003, "FORBIDDEN: " + exc.getMessage()));
        } catch (com.example.csagent.service.InvalidInputException exc) {
            return new McpResponse(400, errorResponse(id, -32602, "INVALID_INPUT: " + exc.getMessage()));
        } catch (NotFoundException exc) {
            // 与 REST 同口径：404 + 服务层原始文案（订单不存在 / 物流信息不存在）
            String message = (exc.getMessage() == null || exc.getMessage().isBlank())
                    ? "资源不存在" : exc.getMessage();
            return new McpResponse(404, errorResponse(id, -32004, message));
        } catch (Exception exc) {
            // 未预期异常：给客户端一个可编程的错误码，而不是自由文本
            return new McpResponse(500, errorResponse(id, -32002,
                    "UNAVAILABLE: 工具执行失败: " + exc.getMessage()));
        }
    }

    private String okResponse(JsonNode id, JsonNode result) {
        ObjectNode response = mapper.createObjectNode();
        response.put("jsonrpc", "2.0");
        response.set("id", id);
        response.set("result", result);
        return response.toString();
    }

    private String errorResponse(JsonNode id, int code, String message) {
        ObjectNode response = mapper.createObjectNode();
        response.put("jsonrpc", "2.0");
        if (id != null) {
            response.set("id", id);
        } else {
            response.putNull("id");
        }
        ObjectNode error = response.putObject("error");
        error.put("code", code);
        error.put("message", message);
        return response.toString();
    }

    private JsonNode initializeResult() {
        ObjectNode result = mapper.createObjectNode();
        result.put("protocolVersion", PROTOCOL_VERSION);
        result.putObject("capabilities").putObject("tools");
        result.putObject("serverInfo").put("name", "cs-agent-business").put("version", "0.1.0");
        return result;
    }

    private JsonNode toolsListResult() {
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

    private JsonNode toolResult(String text, boolean isError) {
        ObjectNode result = mapper.createObjectNode();
        result.putArray("content").addObject().put("type", "text").put("text", text);
        if (isError) {
            result.put("isError", true);
        }
        return result;
    }
}
