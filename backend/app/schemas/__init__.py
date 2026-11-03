"""Pydantic 模型包，统一导出各类输入/输出模型。

Pydantic schemas package exporting input/output models.
"""

from __future__ import annotations

from .category import CategoryCreate, CategoryOut, CategoryUpdate
from .common import ErrorResponse
from .dish import DishAvailabilityUpdate, DishCreate, DishOut, DishUpdate
from .order import (
    OrderCreate,
    OrderCreateResult,
    OrderItemIn,
    OrderItemOut,
    OrderItemStatusUpdate,
    OrderOut,
    OrderStatusUpdate,
    PrintRequest,
    PrintResult,
)
from .settings import (
    PrinterSettings,
    SettingsOut,
    SettingsStatus,
    SettingsUpdate,
)
from .stats import DailyRevenueOut, RevenueStatsOut, TopDishOut

# 对外导出清单 / Public export list
__all__ = [
    "CategoryOut",
    "CategoryCreate",
    "CategoryUpdate",
    "DishOut",
    "DishCreate",
    "DishUpdate",
    "DishAvailabilityUpdate",
    "OrderCreate",
    "OrderCreateResult",
    "OrderItemIn",
    "OrderItemOut",
    "OrderItemStatusUpdate",
    "OrderOut",
    "OrderStatusUpdate",
    "PrintRequest",
    "PrintResult",
    "PrinterSettings",
    "SettingsOut",
    "SettingsStatus",
    "SettingsUpdate",
    "ErrorResponse",
    "DailyRevenueOut",
    "RevenueStatsOut",
    "TopDishOut",
]
