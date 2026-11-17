package com.example.csagent.api;

import jakarta.validation.constraints.NotBlank;

public record AddressRequest(
        @NotBlank(message = "收件人不能为空") String receiver,
        @NotBlank(message = "手机号不能为空") String phone,
        @NotBlank(message = "地址不能为空") String address
) {
}
