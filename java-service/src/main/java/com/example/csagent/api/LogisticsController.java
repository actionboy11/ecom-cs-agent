package com.example.csagent.api;

import com.example.csagent.domain.Logistics;
import com.example.csagent.security.AuthenticatedUser;
import com.example.csagent.service.LogisticsQueryService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/logistics")
public class LogisticsController {

    private final LogisticsQueryService logisticsQueryService;

    public LogisticsController(LogisticsQueryService logisticsQueryService) {
        this.logisticsQueryService = logisticsQueryService;
    }

    @GetMapping("/{orderNo}")
    public Logistics get(@PathVariable String orderNo,
                         @AuthenticationPrincipal AuthenticatedUser user,
                         HttpServletRequest request) {
        return logisticsQueryService.findByOrderNo(orderNo, user, request.getRequestURI());
    }
}
