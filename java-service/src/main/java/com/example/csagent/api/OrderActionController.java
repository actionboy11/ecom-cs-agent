package com.example.csagent.api;

import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.OrderActionService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/orders")
public class OrderActionController {

    private final OrderActionService service;

    public OrderActionController(OrderActionService service) {
        this.service = service;
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
