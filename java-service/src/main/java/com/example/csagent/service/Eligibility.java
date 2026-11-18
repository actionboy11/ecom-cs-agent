package com.example.csagent.service;

import java.time.LocalDate;

/** 售后资格结果：Java API、Agent、前端共用。 */
public record Eligibility(
        boolean allowed,
        String reasonCode,
        String reason,
        String shippingPayer,
        boolean requiresReturnInfo,
        boolean requiresEvidence,
        boolean requiresIntercept,
        String nextAction
) {
    public static Eligibility of(
            boolean allowed, String reasonCode, String reason, String shippingPayer,
            boolean requiresReturnInfo, boolean requiresEvidence,
            boolean requiresIntercept, String nextAction) {
        return new Eligibility(allowed, reasonCode, reason, shippingPayer,
                requiresReturnInfo, requiresEvidence, requiresIntercept, nextAction);
    }

    public static Eligibility denied(String code, String reason, String nextAction) {
        return new Eligibility(false, code, reason, null, false, false, false, nextAction);
    }

    public static Eligibility allowed(
            String code, String reason, String payer,
            boolean returnInfo, boolean evidence, String nextAction) {
        return new Eligibility(true, code, reason, payer, returnInfo, evidence, false, nextAction);
    }

    public boolean isSignedInWindow(LocalDate delivered, LocalDate today, int from, int to) {
        if (delivered == null) {
            return false;
        }
        long days = java.time.temporal.ChronoUnit.DAYS.between(delivered, today);
        return days >= from && days <= to;
    }
}
