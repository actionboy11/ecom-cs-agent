package com.example.csagent.service;

/**
 * 凭据无效。故意不区分「用户不存在」与「密码错误」——两者对外必须不可区分。
 */
public class InvalidCredentialsException extends RuntimeException {
    public InvalidCredentialsException() {
        super("用户名或密码错误");
    }
}
