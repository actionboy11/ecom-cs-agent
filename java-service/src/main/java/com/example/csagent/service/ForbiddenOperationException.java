package com.example.csagent.service;

/** 角色不允许该操作（如坐席发起售后）：REST 映射 403，MCP 映射 -32003。 */
public class ForbiddenOperationException extends RuntimeException {
    public ForbiddenOperationException(String message) {
        super(message);
    }
}
