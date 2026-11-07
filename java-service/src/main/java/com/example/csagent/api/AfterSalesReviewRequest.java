package com.example.csagent.api;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record AfterSalesReviewRequest(
        @NotNull(message = "approved 不能为空")
        Boolean approved,

        @Size(max = 200, message = "备注过长")
        String note
) {
}
