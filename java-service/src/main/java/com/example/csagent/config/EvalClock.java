package com.example.csagent.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.time.LocalDate;

/** 评测时钟：EVAL_TODAY 为空时使用真实日期。 */
@Component
public class EvalClock {

    private final LocalDate fixed;

    public EvalClock(@Value("${app.eval-today:}") String evalToday) {
        this.fixed = parse(evalToday);
    }

    private static LocalDate parse(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return LocalDate.parse(value.trim());
        } catch (RuntimeException ignored) {
            return null;
        }
    }

    public LocalDate today() {
        return fixed != null ? fixed : LocalDate.now();
    }
}
