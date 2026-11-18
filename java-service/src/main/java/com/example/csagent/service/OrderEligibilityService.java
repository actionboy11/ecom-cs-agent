package com.example.csagent.service;

import com.example.csagent.domain.Order;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;

/** 订单状态 × 动作的统一资格判断。 */
@Service
public class OrderEligibilityService {

    public Eligibility check(Order order, String action, boolean quality, boolean intercepted, LocalDate today) {
        String status = order.status();
        String normalized = action == null ? "" : action.trim().toLowerCase();

        if ("address".equals(normalized)) {
            if ("待发货".equals(status)) {
                return Eligibility.allowed("ADDRESS_PENDING", "待发货订单可以修改收货地址",
                        null, false, false, "ADDRESS_FORM");
            }
            return Eligibility.denied("ADDRESS_NOT_PENDING", "订单已发货或已签收，不能修改收货地址", "HANDOFF");
        }

        if ("invoice".equals(normalized)) {
            if (!"已签收".equals(status)) {
                return Eligibility.denied("INVOICE_NOT_SIGNED", "订单未签收，不能开票", "NONE");
            }
            long days = days(order, today);
            if (days <= 30) {
                return Eligibility.allowed("INVOICE_SIGNED_30", "签收 30 天内可以申请发票",
                        null, false, false, "INVOICE_FORM");
            }
            return Eligibility.denied("INVOICE_OVER_30", "签收超过 30 天，不能直接开票", "HANDOFF");
        }

        if ("urge".equals(normalized)) {
            if ("待发货".equals(status) || "已发货".equals(status) || "运输中".equals(status)) {
                return Eligibility.allowed("URGE_ALLOWED", "可以催件", null, false, false, "URGE");
            }
            return Eligibility.denied("URGE_NOT_ALLOWED", "当前订单状态不需要催件", "NONE");
        }

        if (!("refund".equals(normalized) || "return".equals(normalized) || "exchange".equals(normalized))) {
            return Eligibility.denied("UNKNOWN_ACTION", "未知动作", "NONE");
        }

        String tags = order.tags() == null ? "" : order.tags();
        boolean custom = tags.contains("custom") || tags.contains("定制");
        boolean gift = tags.contains("gift") || tags.contains("赠品");
        if (custom && !quality) {
            return Eligibility.denied("CUSTOM_NO_REASON",
                    "定制商品无质量问题，不适用无理由退货", "HANDOFF");
        }
        if (gift) {
            return Eligibility.denied("GIFT_SEPARATE_AFTER_SALES",
                    "赠品单独售后没有明确政策，需人工确认", "HANDOFF");
        }

        if ("已取消".equals(status)) {
            return Eligibility.denied("CANCELLED", "订单已取消，不能创建新的售后", "HANDOFF");
        }

        if ("待发货".equals(status)) {
            if ("refund".equals(normalized)) {
                return Eligibility.allowed("PENDING_REFUND", "待发货订单可以直接退款",
                        null, false, false, "CONFIRM");
            }
            return Eligibility.denied("NOT_APPLICABLE", "待发货订单不需要退货/换货", "NONE");
        }

        if ("已发货".equals(status) || "运输中".equals(status)) {
            if (!intercepted) {
                return new Eligibility(false, "INTERCEPT_REQUIRED",
                        "运输中需要先拦截快递，成功后才能退款", null,
                        false, false, true, "INTERCEPT");
            }
            if ("refund".equals(normalized)) {
                return Eligibility.allowed("INTERCEPTED_REFUND", "拦截成功，可以确认退款",
                        null, false, false, "CONFIRM");
            }
            return Eligibility.denied("INTERCEPTED_RETURN", "拦截成功后按退款处理，不需要退货信息", "CONFIRM");
        }

        if (!"已签收".equals(status)) {
            return Eligibility.denied("UNSUPPORTED_STATUS", "当前订单状态不支持售后", "HANDOFF");
        }

        long days = days(order, today);
        if (days < 0) {
            return Eligibility.denied("INVALID_DELIVERED", "签收时间异常", "HANDOFF");
        }
        if (days <= 7) {
            boolean evidence = quality;
            String payer = quality ? "SELLER" : "BUYER";
            return Eligibility.allowed("SIGNED_0_7",
                    quality ? "签收 0–7 天，质量问题退换" : "签收 0–7 天，无理由退换",
                    payer, true, evidence, formAction(normalized));
        }
        if (days <= 15) {
            if (!quality) {
                return Eligibility.denied("QUALITY_REQUIRED", "签收 8–15 天仅支持质量问题退换", "NONE");
            }
            return Eligibility.allowed("SIGNED_8_15", "签收 8–15 天质量问题，需上传凭证",
                    "SELLER", true, true, formAction(normalized));
        }
        if (days <= 30) {
            return Eligibility.allowed("SIGNED_16_30", "签收 16–30 天，需填写原因，运费买家承担",
                    "BUYER", true, false, formAction(normalized));
        }
        return Eligibility.denied("SIGNED_OVER_30", "签收超过 30 天，不能创建新的售后单", "HANDOFF");
    }

    private static String formAction(String action) {
        return switch (action) {
            case "return" -> "RETURN_FORM";
            case "exchange" -> "EXCHANGE_FORM";
            default -> "RETURN_FORM";
        };
    }

    private static long days(Order order, LocalDate today) {
        if (order.deliveredAt() == null) {
            return Long.MIN_VALUE;
        }
        return ChronoUnit.DAYS.between(order.deliveredAt().toLocalDate(), today);
    }
}
