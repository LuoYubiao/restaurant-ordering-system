"""营业统计相关的 Pydantic 模型。

Pydantic schemas for revenue statistics.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DailyRevenueOut(BaseModel):
    """每日营业额输出模型。

    Daily revenue output schema.
    """

    # 日期（YYYY-MM-DD）/ Date (YYYY-MM-DD)
    date: str
    # 当日营业额（元，两位小数字符串）/ Daily revenue in yuan as a 2-decimal string
    amount: str
    # 当日已结账单数 / Settled order count of the day
    orderCount: int


class TopDishOut(BaseModel):
    """菜品销量排行输出模型。

    Ranked dish output schema.
    """

    # 菜品 ID / Dish id
    dishId: int
    # 菜品名称（最新快照）/ Dish name (latest snapshot)
    dishName: str
    # 销量份数 / Sold quantity
    quantity: int
    # 销售额（元，两位小数字符串）/ Sales amount in yuan as a 2-decimal string
    amount: str


class RevenueStatsOut(BaseModel):
    """营业额统计输出模型。

    Revenue statistics output schema.
    """

    # 区间标识 / Range identifier
    range: str
    # 起始日期（YYYY-MM-DD）/ Start date (YYYY-MM-DD)
    startDate: str
    # 结束日期（YYYY-MM-DD）/ End date (YYYY-MM-DD)
    endDate: str
    # 营业额合计（元）/ Total revenue in yuan
    totalAmount: str
    # 已结账单数 / Settled order count
    orderCount: int
    # 客单价（元），单数为 0 时为 null / Average order value, null when there is no order
    averageAmount: Optional[str] = None
    # 每日趋势 / Daily trend
    daily: List[DailyRevenueOut] = Field(default_factory=list)
    # 菜品销量排行 / Dish ranking
    topDishes: List[TopDishOut] = Field(default_factory=list)
