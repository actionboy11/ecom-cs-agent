package com.example.csagent.bootstrap;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.csagent.domain.UserEntity;
import com.example.csagent.store.UserMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 演示账号播种：迁移脚本里密码是占位符 {@code __PENDING__}，
 * 启动时用 BCrypt 生成真实哈希写回。幂等——已经填过的不再改动。
 */
@Component
public class UserSeeder implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(UserSeeder.class);
    private static final String PLACEHOLDER = "__PENDING__";
    static final String DEMO_PASSWORD = "demo123";
    private static final List<String> DEMO_USERS = List.of("buyer_a", "buyer_b", "buyer_c", "cs_agent");

    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;

    public UserSeeder(UserMapper userMapper, PasswordEncoder passwordEncoder) {
        this.userMapper = userMapper;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(ApplicationArguments args) {
        int seeded = 0;
        for (String username : DEMO_USERS) {
            UserEntity user = userMapper.selectOne(
                    new LambdaQueryWrapper<UserEntity>().eq(UserEntity::getUsername, username));
            if (user == null) {
                log.warn("演示账号 {} 不在 users 表中，跳过（请检查 Flyway 种子数据）", username);
                continue;
            }
            if (PLACEHOLDER.equals(user.getPasswordHash())) {
                user.setPasswordHash(passwordEncoder.encode(DEMO_PASSWORD));
                userMapper.updateById(user);
                seeded++;
            }
        }
        if (seeded > 0) {
            log.info("已为 {} 个演示账号写入 BCrypt 密码哈希", seeded);
        }
    }
}
