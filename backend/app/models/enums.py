"""枚举与中文文案映射模块。

Enumerations and Chinese text mappings.

枚举值本身为稳定的英文标识（用于存储与接口），同时提供对外的中文文案映射。
Enum values are stable English identifiers (used for storage and APIs), while
Chinese display texts are provided separately.
"""

from __future__ import annotations

from enum import Enum


class OrderStatus(str, Enum):
    """订单状态枚举。

    Order status enumeration.
    """

    # 待接单 / Waiting to be accepted
    PENDING = "pending"
    # 制作中 / Being prepared
    COOKING = "cooking"
    # 已出餐 / Served
    COMPLETED = "completed"
    # 已结账 / Settled
    SETTLED = "settled"
    # 已取消 / Cancelled
    CANCELLED = "cancelled"


class OrderItemStatus(str, Enum):
    """订单明细状态枚举。

    Order item status enumeration.
    """

    # 待出餐 / Waiting to be served
    PENDING = "pending"
    # 已出餐 / Served
    COMPLETED = "completed"


class DiningType(str, Enum):
    """就餐方式枚举。

    Dining type enumeration.
    """

    # 堂食 / Dine in
    DINE_IN = "dine_in"
    # 打包 / Takeaway
    TAKEAWAY = "takeaway"


# 订单状态中文文案 / Chinese text for order statuses
ORDER_STATUS_TEXT: dict[str, str] = {
    OrderStatus.PENDING.value: "待接单",
    OrderStatus.COOKING.value: "制作中",
    OrderStatus.COMPLETED.value: "已出餐",
    OrderStatus.SETTLED.value: "已结账",
    OrderStatus.CANCELLED.value: "已取消",
}

# 就餐方式中文文案 / Chinese text for dining types
DINING_TYPE_TEXT: dict[str, str] = {
    DiningType.DINE_IN.value: "堂食",
    DiningType.TAKEAWAY.value: "打包",
}

# 订单明细状态中文文案 / Chinese text for order item statuses
ORDER_ITEM_STATUS_TEXT: dict[str, str] = {
    OrderItemStatus.PENDING.value: "待出餐",
    OrderItemStatus.COMPLETED.value: "已出餐",
}
