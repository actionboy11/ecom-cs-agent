package com.example.csagent.service;

/**
 * 状态冲突：例如对已审批的售后申请再次审批。按 S2-2 的决定，不约定具体状态码，
 * 由 ApiExceptionHandler 统一映射为 409。
 */
public class StateConflictException extends RuntimeException {
    public StateConflictException(String message) {
        super(message);
    }
}
