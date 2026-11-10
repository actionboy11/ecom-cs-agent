package com.example.csagent.service;

/** 参数非法（非法枚举值等）：REST 400，MCP -32602 + INVALID_INPUT。 */
public class InvalidInputException extends RuntimeException {
    public InvalidInputException(String message) {
        super(message);
    }
}
