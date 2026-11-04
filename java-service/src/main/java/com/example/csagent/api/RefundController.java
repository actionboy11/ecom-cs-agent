package com.example.csagent.api;

import com.example.csagent.domain.Refund;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.AfterSalesService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 售后申请。本切片仍沿用 /api/refunds 路径以保持行为一致；
 * S2-2 会改为 SPEC 定义的 /api/after-sales 并支持三种类型。
 */
@RestController
@RequestMapping("/api/refunds")
public class RefundController {

    private final AfterSalesService afterSalesService;

    public RefundController(AfterSalesService afterSalesService) {
        this.afterSalesService = afterSalesService;
    }

    @PostMapping
    public Refund create(@Valid @RequestBody RefundRequest request,
                         @AuthenticationPrincipal AuthenticatedUser user,
                         HttpServletRequest httpRequest) {
        return afterSalesService.createRefund(request.orderNo(), request.reason(), user, httpRequest.getRequestURI());
    }
}
