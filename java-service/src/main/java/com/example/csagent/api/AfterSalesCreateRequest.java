package com.example.csagent.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record AfterSalesCreateRequest(
        @NotBlank(message = "orderNo 不能为空")
        String orderNo,

        @NotBlank(message = "type 不能为空")
        String type,

        @NotBlank(message = "售后原因不能为空")
        @Size(max = 200, message = "原因过长")
        String reason
) {
}
