package com.example.csagent.api;

import com.example.csagent.domain.Order;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.OrderQueryService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderQueryService orderQueryService;

    public OrderController(OrderQueryService orderQueryService) {
        this.orderQueryService = orderQueryService;
    }

    /** 列表：买家只看自己的，坐席看全部。 */
    @GetMapping
    public List<Order> list(@AuthenticationPrincipal AuthenticatedUser user) {
        return orderQueryService.listFor(user);
    }

    @GetMapping("/{orderNo}")
    public Order get(@PathVariable String orderNo,
                     @AuthenticationPrincipal AuthenticatedUser user,
                     HttpServletRequest request) {
        return orderQueryService.findByOrderNo(orderNo, user, request.getRequestURI());
    }
}
