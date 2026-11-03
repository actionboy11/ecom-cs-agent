package com.example.csagent.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.api.AuthResponse;
import com.example.csagent.domain.UserEntity;
import com.example.csagent.security.JwtService;
import com.example.csagent.store.UserMapper;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class AuthService {

    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    /** 用户不存在时也跑一次哈希比对，避免通过响应时间判断账号是否存在。 */
    private final String dummyHash;

    public AuthService(UserMapper userMapper, PasswordEncoder passwordEncoder, JwtService jwtService) {
        this.userMapper = userMapper;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
        this.dummyHash = passwordEncoder.encode("dummy-password-for-timing");
    }

    public AuthResponse login(String username, String password) {
        UserEntity user = userMapper.selectOne(
                new LambdaQueryWrapper<UserEntity>().eq(UserEntity::getUsername, username));
        String hash = user == null ? dummyHash : user.getPasswordHash();
        boolean passwordMatches = passwordEncoder.matches(password, hash);
        if (user == null || !passwordMatches) {
            throw new InvalidCredentialsException();
        }
        return new AuthResponse(jwtService.issue(user), user.getRole(), user.getDisplayName(), user.getId());
    }
}
