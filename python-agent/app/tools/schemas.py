"""工具返回结构（与 Java 业务系统约定一致）。

W2 把这里换成真正的 MCP 工具后，这些 schema 会变成 tool 的 output schema，
所以现在就把字段定清楚，避免后期返工。
"""

from typing import Literal

from pydantic import BaseModel, Field


class OrderInfo(BaseModel):
    orderNo: str = Field(description="订单号")
    item: str = Field(description="商品名称")
    amount: float = Field(description="订单金额")
    status: str = Field(description="订单状态")
    createdAt: str = Field(description="下单日期")


class LogisticsInfo(BaseModel):
    orderNo: str
    carrier: str = Field(description="承运商")
    trackingNo: str = Field(description="运单号")
    status: str = Field(description="物流状态")
    traces: list[str] = Field(default_factory=list, description="物流轨迹")


class AfterSalesRequestResult(BaseModel):
    requestNo: str
    orderNo: str
    type: Literal["REFUND", "RETURN", "EXCHANGE"]
    reason: str
    status: Literal["PENDING", "APPROVED", "REJECTED"]
    createdAt: str


class ProductInfo(BaseModel):
    sku: str
    name: str
    price: float
    attrs: dict[str, str] = Field(default_factory=dict, description="商品参数，键为中文")
    stock: int = Field(description="库存")
    faq: list[str] = Field(default_factory=list)


class ToolError(BaseModel):
    tool: str
    error: str
    recoverable: bool = True
