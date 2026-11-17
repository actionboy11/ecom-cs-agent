package com.example.csagent.api;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

public record InvoiceRequest(
        @NotBlank(message = "发票抬头不能为空") String title,
        @NotBlank(message = "税号不能为空") String taxId,
        @Email(message = "邮箱格式不正确") String email
) {
}
