"""订单相关的 Pydantic 模型。

Pydantic schemas for orders.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class OrderItemIn(BaseModel):
    """下单时的菜品明细输入。

    Order item input when creating an order.
    """

    # 菜品 ID / Dish id
    dishId: int
    # 数量（至少 1）/ Quantity (at least 1)
    quantity: int = Field(ge=1)
    # 口味/特殊要求备注 / Taste or special-request remark
    remark: Optional[str] = None


class OrderCreate(BaseModel):
    """创建订单的输入模型。

    Order creation input schema.
    """

    # 桌号，打包订单可为空 / Table number, may be null for takeaway
    tableNo: Optional[str] = None
    # 就餐方式：dine_in / takeaway / Dining type: dine_in / takeaway
    diningType: str = "dine_in"
    # 订单备注 / Order remark
    remark: Optional[str] = None
    # 前端可传总金额（元字符串），不传则由后端计算 / Optional client-side total in yuan
    totalAmount: Optional[str] = None
    # 订单明细（至少一项）/ Order items (at least one)
    items: List[OrderItemIn] = Field(min_length=1)


class OrderItemOut(BaseModel):
    """订单明细输出模型。

    Order item output schema.
    """

    model_config = ConfigDict(from_attributes=True)

    # 明细 ID / Item id
    id: int
    # 菜品 ID / Dish id
    dishId: int
    # 菜品名称 / Dish name
    dishName: str
    # 单价（元，两位小数字符串）/ Unit price in yuan as a 2-decimal string
    price: str
    # 数量 / Quantity
    quantity: int
    # 口味备注 / Taste remark
    remark: Optional[str] = None
    # 明细状态 / Item status
    status: str
    # 明细状态中文文案 / Chinese text of item status
    statusText: str
    # 出餐完成时间 / Completion time
    completedTime: Optional[str] = None


class OrderOut(BaseModel):
    """订单输出模型。

    Order output schema.
    """

    model_config = ConfigDict(from_attributes=True)

    # 订单 ID / Order id
    id: int
    # 订单号 / Order number
    orderNo: str
    # 桌号 / Table number
    tableNo: Optional[str] = None
    # 就餐方式 / Dining type
    diningType: str
    # 就餐方式中文文案 / Chinese text of dining type
    diningTypeText: str
    # 订单状态 / Order status
    status: str
    # 订单状态中文文案 / Chinese text of order status
    statusText: str
    # 订单总金额（元，两位小数字符串）/ Total amount in yuan as a 2-decimal string
    totalAmount: str
    # 订单备注 / Order remark
    remark: Optional[str] = None
    # 打印次数 / Print count
    printCount: int = 0
    # 明细总数 / Total item count
    itemCount: int = 0
    # 已完成明细数 / Completed item count
    completedCount: int = 0
    # 创建时间（ISO 字符串）/ Created time (ISO string)
    createdTime: str
    # 更新时间（ISO 字符串）/ Updated time (ISO string)
    updatedTime: str
    # 明细列表 / Item list
    items: List[OrderItemOut] = Field(default_factory=list)


class OrderStatusUpdate(BaseModel):
    """更新订单状态的输入模型。

    Order status update input schema.
    """

    # 目标状态 / Target status
    status: str


class OrderItemStatusUpdate(BaseModel):
    """更新订单明细状态的输入模型。

    Order item status update input schema.
    """

    # 目标状态 / Target status
    status: str


class PrintRequest(BaseModel):
    """手动补打请求模型。

    Manual reprint request schema.
    """

    # 打印目标：counter / kitchen / both / Print target: counter / kitchen / both
    target: str = "both"


class PrintResult(BaseModel):
    """单次打印结果模型。

    Single print result schema.
    """

    # 打印目标 / Print target
    target: str
    # 是否成功 / Whether succeeded
    ok: bool
    # 结果说明（成功或失败原因）/ Result message (success or failure reason)
    message: str


class OrderCreateResult(BaseModel):
    """创建订单的返回模型（含打印结果）。

    Order creation result schema (including print results).
    """

    # 订单详情 / Order detail
    order: OrderOut
    # 打印结果列表 / Print result list
    printResults: List[PrintResult] = Field(default_factory=list)
