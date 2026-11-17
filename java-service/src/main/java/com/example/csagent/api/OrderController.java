package com.example.csagent.api;

import com.example.csagent.domain.Order;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.OrderQueryService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.example.csagent.service.InvalidInputException;

import java.time.LocalDate;
import java.util.Comparator;
import java.util.stream.Collectors;

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
    public List<Order> list(@AuthenticationPrincipal AuthenticatedUser user, HttpServletRequest request) {
        return orderQueryService.listFor(user, request.getRequestURI());
    }

    @GetMapping("/page")
    public OrderPage page(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "10") int pageSize,
            @RequestParam(name = "created_from", required = false) String createdFrom,
            @RequestParam(name = "created_to", required = false) String createdTo,
            @RequestParam(required = false) String product,
            @RequestParam(required = false) String status,
            @AuthenticationPrincipal AuthenticatedUser user,
            HttpServletRequest request) {
        int safePage = Math.max(1, page);
        int safeSize = Math.max(1, Math.min(50, pageSize));
        LocalDate from = parseDate(createdFrom);
        LocalDate to = parseDate(createdTo);
        List<Order> filtered = orderQueryService.listFor(user, request.getRequestURI()).stream()
                .filter(order -> from == null || !order.createdAt().isBefore(from))
                .filter(order -> to == null || !order.createdAt().isAfter(to))
                .filter(order -> product == null || product.isBlank() || order.item().contains(product))
                .filter(order -> status == null || status.isBlank() || status.equals(order.status()))
                .sorted(Comparator.comparing(Order::createdAt).reversed()
                        .thenComparing(Order::orderNo, Comparator.reverseOrder()))
                .collect(Collectors.toList());
        int start = Math.min(filtered.size(), (safePage - 1) * safeSize);
        int end = Math.min(filtered.size(), start + safeSize);
        return new OrderPage(filtered.subList(start, end), filtered.size(), safePage, safeSize,
                end < filtered.size());
    }

    private static LocalDate parseDate(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return LocalDate.parse(value);
        } catch (RuntimeException ex) {
            throw new InvalidInputException("日期格式必须是 yyyy-MM-dd: " + value);
        }
    }

    @GetMapping("/{orderNo}")
    public Order get(@PathVariable String orderNo,
                     @AuthenticationPrincipal AuthenticatedUser user,
                     HttpServletRequest request) {
        return orderQueryService.findByOrderNo(orderNo, user, request.getRequestURI());
    }
}
