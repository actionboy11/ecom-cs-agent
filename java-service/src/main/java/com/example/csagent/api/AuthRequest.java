package com.example.csagent.api;

import jakarta.validation.constraints.NotBlank;

public record AuthRequest(
        @NotBlank(message = "username 不能为空") String username,
        @NotBlank(message = "password 不能为空") String password
) {
}
