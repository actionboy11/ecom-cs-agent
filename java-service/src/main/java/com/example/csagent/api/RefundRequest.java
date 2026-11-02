package com.example.csagent.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record RefundRequest(
        @NotBlank(message = "orderNo 不能为空")
        String orderNo,

        @Size(max = 200, message = "原因过长")
        String reason
) {
}
