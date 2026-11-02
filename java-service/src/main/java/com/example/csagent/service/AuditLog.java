package com.example.csagent.service;

import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentLinkedDeque;

/**
 * 操作审计：Agent 的每一次工具调用都要留下痕迹。
 * 面试可讲点：Agent 调业务系统必须有「谁、什么时候、干了什么」的可追溯链路。
 */
@Service
public class AuditLog {

    private static final int MAX_SIZE = 500;

    private final Deque<Map<String, Object>> entries = new ConcurrentLinkedDeque<>();

    public void record(String action, String target, Map<String, Object> detail) {
        entries.addFirst(Map.of(
                "ts", LocalDateTime.now().withNano(0).toString(),
                "action", action,
                "target", target,
                "detail", detail == null ? Map.of() : detail
        ));
        while (entries.size() > MAX_SIZE) {
            entries.removeLast();
        }
    }

    public List<Map<String, Object>> recent(int limit) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> entry : entries) {
            if (result.size() >= limit) {
                break;
            }
            result.add(entry);
        }
        return result;
    }
}
