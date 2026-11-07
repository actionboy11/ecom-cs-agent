package com.example.csagent.api;

import com.example.csagent.domain.AfterSalesRequest;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.AfterSalesService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 售后接口（SPEC §6.2）：
 * POST /api/after-sales              买家发起（REFUND / RETURN / EXCHANGE）
 * POST /api/after-sales/{no}/review  坐席审批
 */
@RestController
@RequestMapping("/api/after-sales")
public class AfterSalesController {

    private final AfterSalesService afterSalesService;

    public AfterSalesController(AfterSalesService afterSalesService) {
        this.afterSalesService = afterSalesService;
    }

    @PostMapping
    public AfterSalesRequest create(@Valid @RequestBody AfterSalesCreateRequest request,
                                    @AuthenticationPrincipal AuthenticatedUser user,
                                    HttpServletRequest httpRequest) {
        return afterSalesService.create(request.orderNo(), request.type(), request.reason(),
                user, httpRequest.getRequestURI());
    }

    @PostMapping("/{requestNo}/review")
    public AfterSalesRequest review(@PathVariable String requestNo,
                                    @Valid @RequestBody AfterSalesReviewRequest request,
                                    @AuthenticationPrincipal AuthenticatedUser user,
                                    HttpServletRequest httpRequest) {
        return afterSalesService.review(requestNo, Boolean.TRUE.equals(request.approved()),
                request.note(), user, httpRequest.getRequestURI());
    }
}
