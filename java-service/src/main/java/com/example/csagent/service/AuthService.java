package com.example.csagent.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.api.AuthResponse;
import com.example.csagent.domain.UserEntity;
import com.example.csagent.security.JwtService;
import com.example.csagent.store.UserMapper;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.Map;

@Service
public class AuthService {

    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final AuditService auditService;
    /** 用户不存在时也跑一次哈希比对，避免通过响应时间判断账号是否存在。 */
    private final String dummyHash;

    public AuthService(UserMapper userMapper, PasswordEncoder passwordEncoder,
                       JwtService jwtService, AuditService auditService) {
        this.userMapper = userMapper;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
        this.auditService = auditService;
        this.dummyHash = passwordEncoder.encode("dummy-password-for-timing");
    }

    private static final int AUDIT_FIELD_MAX = 50;

    private static String clip(String value) {
        return value == null || value.length() <= AUDIT_FIELD_MAX ? value : value.substring(0, AUDIT_FIELD_MAX);
    }

    public AuthResponse login(String username, String password) {
        UserEntity user = userMapper.selectOne(
                new LambdaQueryWrapper<UserEntity>().eq(UserEntity::getUsername, username));
        String hash = user == null ? dummyHash : user.getPasswordHash();
        boolean passwordMatches = passwordEncoder.matches(password, hash);
        if (user == null || !passwordMatches) {
            // 失败原因统一为 credentials：不区分「用户不存在」与「密码错误」，避免审计成为枚举渠道
            auditService.recordQuietly(AuditEvent.of(
                    clip(username), "", AuditEvent.ACTION_LOGIN, "USER", clip(username),
                    AuditEvent.RESULT_DENIED, "/api/auth/login",
                    Map.of("reason", "credentials")));
            throw new InvalidCredentialsException();
        }
        auditService.recordQuietly(AuditEvent.of(
                user.getUsername(), "", AuditEvent.ACTION_LOGIN, "USER", user.getUsername(),
                AuditEvent.RESULT_OK, "/api/auth/login", Map.of()));
        return new AuthResponse(jwtService.issue(user), user.getRole(), user.getDisplayName(), user.getId());
    }
}
