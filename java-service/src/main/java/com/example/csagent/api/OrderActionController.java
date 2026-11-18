package com.example.csagent.api;

import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.config.EvalClock;
import com.example.csagent.domain.Order;
import com.example.csagent.service.Eligibility;
import com.example.csagent.service.OrderActionService;
import com.example.csagent.service.OrderEligibilityService;
import com.example.csagent.service.OrderQueryService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/orders")
public class OrderActionController {

    private final OrderActionService service;
    private final OrderQueryService orderQueryService;
    private final OrderEligibilityService eligibilityService;
    private final EvalClock clock;

    public OrderActionController(
            OrderActionService service,
            OrderQueryService orderQueryService,
            OrderEligibilityService eligibilityService,
            EvalClock clock) {
        this.service = service;
        this.orderQueryService = orderQueryService;
        this.eligibilityService = eligibilityService;
        this.clock = clock;
    }

    @GetMapping("/{orderNo}/eligibility")
    public Eligibility eligibility(
            @PathVariable String orderNo,
            @RequestParam String action,
            @RequestParam(defaultValue = "false") boolean quality,
            @RequestParam(defaultValue = "false") boolean intercepted,
            @AuthenticationPrincipal AuthenticatedUser user,
            HttpServletRequest httpRequest) {
        Order order = orderQueryService.findByOrderNo(orderNo, user, httpRequest.getRequestURI());
        return eligibilityService.check(order, action, quality, intercepted, clock.today());
    }

    @PostMapping("/{orderNo}/address")
    public Map<String, Object> updateAddress(
            @PathVariable String orderNo,
            @Valid @RequestBody AddressRequest request,
            @AuthenticationPrincipal AuthenticatedUser user,
            HttpServletRequest httpRequest) {
        return service.updateAddress(
                orderNo, request.receiver(), request.phone(), request.address(),
                user, httpRequest.getRequestURI());
    }

    @PostMapping("/{orderNo}/invoice")
    public Map<String, Object> createInvoice(
            @PathVariable String orderNo,
            @Valid @RequestBody InvoiceRequest request,
            @AuthenticationPrincipal AuthenticatedUser user,
            HttpServletRequest httpRequest) {
        return service.createInvoice(
                orderNo, request.title(), request.taxId(), request.email(),
                user, httpRequest.getRequestURI());
    }
}
