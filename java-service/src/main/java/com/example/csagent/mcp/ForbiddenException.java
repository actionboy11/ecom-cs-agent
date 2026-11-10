package com.example.csagent.mcp;

/** 角色不允许该操作：映射为 HTTP 403。 */
public class ForbiddenException extends RuntimeException {
    public ForbiddenException(String message) {
        super(message);
    }
}
