package com.example.csagent.mcp;

import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;

/**
 * MCP stdio 模式的输出通道。
 *
 * <p>stdio 传输要求 stdout 只承载 JSON-RPC 消息，因此启动时把 JVM 的
 * `System.out` 整体重定向到 stderr，并保留原始 stdout 作为协议通道。
 */
public final class McpIo {

    private static volatile PrintStream protocol = System.out;

    private McpIo() {
    }

    public static boolean stdioMode() {
        return "1".equals(System.getenv("MCP_STDIO"));
    }

    public static void enable() {
        protocol = System.out;
        System.setOut(new PrintStream(new FileOutputStream(FileDescriptor.err), true, StandardCharsets.UTF_8));
    }

    public static PrintStream protocol() {
        return protocol;
    }
}
