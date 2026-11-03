package com.example.csagent.api;

public record AuthResponse(
        String token,
        String role,
        String displayName,
        long userId
) {
}
