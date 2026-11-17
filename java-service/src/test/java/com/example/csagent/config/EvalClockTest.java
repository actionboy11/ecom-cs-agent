package com.example.csagent.config;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;

class EvalClockTest {

    @Test
    void fixed_date_is_used_when_configured() {
        EvalClock clock = new EvalClock("2026-11-15");
        assertThat(clock.today()).isEqualTo(LocalDate.of(2026, 11, 15));
    }

    @Test
    void blank_uses_real_date() {
        EvalClock clock = new EvalClock("");
        assertThat(clock.today()).isEqualTo(LocalDate.now());
    }

    @Test
    void invalid_value_falls_back_to_real_date() {
        EvalClock clock = new EvalClock("not-a-date");
        assertThat(clock.today()).isEqualTo(LocalDate.now());
    }
}
