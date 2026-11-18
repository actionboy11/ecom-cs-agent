package com.example.csagent.service;

import com.example.csagent.domain.Order;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;

class OrderEligibilityServiceTest {

    private final OrderEligibilityService service = new OrderEligibilityService();
    private final LocalDate today = LocalDate.of(2026, 11, 15);

    private Order order(String status, int deliveredDaysAgo) {
        LocalDateTime delivered = deliveredDaysAgo < 0
                ? null
                : today.minusDays(deliveredDaysAgo).atTime(15, 0);
        return new Order("CS2024001", "SKU1004", "保温杯", new BigDecimal("129"),
                status, today.minusDays(10), delivered, null);
    }

    @Test
    void pending_refund_allowed() {
        Eligibility result = service.check(order("待发货", -1), "refund", false, false, today);
        assertThat(result.allowed()).isTrue();
        assertThat(result.reasonCode()).isEqualTo("PENDING_REFUND");
    }

    @Test
    void pending_return_denied() {
        assertThat(service.check(order("待发货", -1), "return", false, false, today).allowed()).isFalse();
    }

    @Test
    void transit_requires_intercept() {
        Eligibility result = service.check(order("运输中", -1), "refund", false, false, today);
        assertThat(result.allowed()).isFalse();
        assertThat(result.requiresIntercept()).isTrue();
        assertThat(result.nextAction()).isEqualTo("INTERCEPT");
    }

    @Test
    void transit_after_intercept_allows_refund() {
        Eligibility result = service.check(order("运输中", -1), "refund", false, true, today);
        assertThat(result.allowed()).isTrue();
        assertThat(result.reasonCode()).isEqualTo("INTERCEPTED_REFUND");
    }

    @Test
    void signed_6_days_no_reason_buyer_pays() {
        Eligibility result = service.check(order("已签收", 6), "return", false, false, today);
        assertThat(result.allowed()).isTrue();
        assertThat(result.shippingPayer()).isEqualTo("BUYER");
        assertThat(result.requiresEvidence()).isFalse();
    }

    @Test
    void signed_6_days_quality_seller_pays() {
        Eligibility result = service.check(order("已签收", 6), "return", true, false, today);
        assertThat(result.allowed()).isTrue();
        assertThat(result.shippingPayer()).isEqualTo("SELLER");
    }

    @Test
    void signed_10_days_requires_quality() {
        assertThat(service.check(order("已签收", 10), "return", false, false, today).allowed()).isFalse();
        assertThat(service.check(order("已签收", 10), "return", true, false, today).allowed()).isTrue();
    }

    @Test
    void signed_20_days_buyer_pays() {
        Eligibility result = service.check(order("已签收", 20), "return", false, false, today);
        assertThat(result.allowed()).isTrue();
        assertThat(result.shippingPayer()).isEqualTo("BUYER");
        assertThat(result.requiresEvidence()).isFalse();
    }

    @Test
    void signed_over_30_days_denied() {
        Eligibility result = service.check(order("已签收", 31), "return", false, false, today);
        assertThat(result.allowed()).isFalse();
        assertThat(result.reasonCode()).isEqualTo("SIGNED_OVER_30");
    }

    @Test
    void invoice_30_days_allowed_31_denied() {
        assertThat(service.check(order("已签收", 30), "invoice", false, false, today).allowed()).isTrue();
        assertThat(service.check(order("已签收", 31), "invoice", false, false, today).allowed()).isFalse();
    }

    @Test
    void address_only_pending() {
        assertThat(service.check(order("待发货", -1), "address", false, false, today).allowed()).isTrue();
        assertThat(service.check(order("运输中", -1), "address", false, false, today).allowed()).isFalse();
    }

    @Test
    void urge_only_before_signed() {
        assertThat(service.check(order("运输中", -1), "urge", false, false, today).allowed()).isTrue();
        assertThat(service.check(order("已签收", 2), "urge", false, false, today).allowed()).isFalse();
    }
}
