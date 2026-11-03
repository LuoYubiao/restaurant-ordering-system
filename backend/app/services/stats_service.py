"""营业统计业务服务模块。

Revenue statistics business service module.

集中实现营业额统计口径：区间解析、按日聚合、菜品销量排行，供 API 层调用。
All revenue statistics logic lives here: range resolution, per-day aggregation and
dish ranking, so the API layer stays thin.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Order, OrderItem, OrderStatus
from ..money import fen_to_yuan

# 预设区间标识 / Preset range identifiers
RANGE_TODAY = "today"
RANGE_7D = "7d"
RANGE_30D = "30d"
RANGE_CUSTOM = "custom"

# 预设区间天数 / Day counts of the preset ranges
_PRESET_DAYS: Dict[str, int] = {
    RANGE_TODAY: 1,
    RANGE_7D: 7,
    RANGE_30D: 30,
}

# 自定义区间跨度上限（含首尾）/ Max custom span in days (inclusive)
MAX_CUSTOM_DAYS = 366

# 菜品排行条数上限 / Max number of ranked dishes
TOP_DISH_LIMIT = 10

# 日期输入格式 / Date input format
_DATE_FORMAT = "%Y-%m-%d"


@dataclass(frozen=True)
class DateRange:
    """统计区间（左闭右开）。

    Statistics range (left-closed, right-open).
    """

    # 区间标识 / Range identifier
    range_name: str
    # 起始时间（含）/ Start datetime (inclusive)
    start: datetime
    # 结束时间（不含）/ End datetime (exclusive)
    end: datetime
    # 展示用起始日期 / Display start date
    start_date: date
    # 展示用结束日期（含）/ Display end date (inclusive)
    end_date: date

    @property
    def days(self) -> int:
        """区间天数（含首尾）。

        Number of days covered by the range (inclusive).

        :return: 天数 / day count
        """
        return (self.end_date - self.start_date).days + 1


def _parse_date(value: Optional[str], label: str) -> date:
    """解析 ``YYYY-MM-DD`` 日期字符串。

    Parse a ``YYYY-MM-DD`` date string.

    :param value: 日期字符串 / date string
    :param label: 字段中文名，用于错误提示 / Chinese field name for error text
    :return: 日期对象 / date object
    :raises ValueError: 缺失或格式非法 / when missing or malformed
    """
    if not value or not str(value).strip():
        raise ValueError(f"{label}不能为空，格式为 YYYY-MM-DD")
    try:
        return datetime.strptime(str(value).strip(), _DATE_FORMAT).date()
    except ValueError as exc:
        raise ValueError(f"{label}格式非法：{value!r}，应为 YYYY-MM-DD") from exc


def resolve_range(
    range_name: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    now: Optional[datetime] = None,
) -> DateRange:
    """把区间参数解析为统一的左闭右开时间范围。

    Resolve the range arguments into a unified left-closed right-open time span.

    :param range_name: 区间标识 / range identifier
    :param start: 自定义起始日期 / custom start date
    :param end: 自定义结束日期 / custom end date
    :param now: 基准时间，默认当前时间 / base time, defaults to now
    :return: 统计区间 / resolved date range
    :raises ValueError: 区间非法 / when the range is invalid
    """
    current = now or datetime.now()
    normalized = (range_name or RANGE_TODAY).strip().lower()

    if normalized == RANGE_CUSTOM:
        start_date = _parse_date(start, "起始日期")
        end_date = _parse_date(end, "结束日期")
        if start_date > end_date:
            raise ValueError("起始日期不能晚于结束日期")
        span_days = (end_date - start_date).days + 1
        if span_days > MAX_CUSTOM_DAYS:
            raise ValueError(f"查询跨度最多 {MAX_CUSTOM_DAYS} 天，当前为 {span_days} 天")
    elif normalized in _PRESET_DAYS:
        span_days = _PRESET_DAYS[normalized]
        end_date = current.date()
        start_date = end_date - timedelta(days=span_days - 1)
    else:
        allowed = "、".join([RANGE_TODAY, RANGE_7D, RANGE_30D, RANGE_CUSTOM])
        raise ValueError(f"不支持的统计区间：{range_name!r}，可选值为 {allowed}")

    return DateRange(
        range_name=normalized,
        start=datetime.combine(start_date, time.min),
        end=datetime.combine(end_date + timedelta(days=1), time.min),
        start_date=start_date,
        end_date=end_date,
    )


def _daily_rows(db: Session, span: DateRange) -> List[Tuple[str, int, int]]:
    """按日聚合已结账订单。

    Aggregate settled orders per day.

    :param db: 数据库会话 / database session
    :param span: 统计区间 / statistics range
    :return: ``(日期, 金额合计（分）, 订单数)`` 列表 / list of ``(date, amount in fen, order count)``
    """
    day_column = func.date(Order.CreatedTime)
    statement = (
        select(day_column, func.sum(Order.TotalAmount), func.count(Order.Id))
        .where(
            Order.Status == OrderStatus.SETTLED.value,
            Order.CreatedTime >= span.start,
            Order.CreatedTime < span.end,
        )
        .group_by(day_column)
        .order_by(day_column)
    )
    return [
        (str(row[0]), int(row[1] or 0), int(row[2] or 0))
        for row in db.execute(statement).all()
    ]


def _top_dishes(db: Session, span: DateRange) -> List[Dict[str, Any]]:
    """按菜品聚合销量与金额，返回销量排行。

    Aggregate quantity and amount per dish and return the ranking.

    :param db: 数据库会话 / database session
    :param span: 统计区间 / statistics range
    :return: 排行列表 / ranking list
    """
    amount_expression = func.sum(OrderItem.Quantity * OrderItem.Price)
    quantity_expression = func.sum(OrderItem.Quantity)
    statement = (
        select(
            OrderItem.DishId,
            quantity_expression.label("quantity"),
            amount_expression.label("amount_fen"),
            func.max(OrderItem.Id).label("last_item_id"),
        )
        .join(Order, Order.Id == OrderItem.OrderId)
        .where(
            Order.Status == OrderStatus.SETTLED.value,
            Order.CreatedTime >= span.start,
            Order.CreatedTime < span.end,
        )
        .group_by(OrderItem.DishId)
        .order_by(
            amount_expression.desc(),
            quantity_expression.desc(),
            OrderItem.DishId.asc(),
        )
        .limit(TOP_DISH_LIMIT)
    )
    rows = db.execute(statement).all()
    if not rows:
        return []

    # 取每组最新一条明细的菜名快照 / Latest dish-name snapshot of each group
    last_item_ids = [int(row[3]) for row in rows]
    name_rows = db.execute(
        select(OrderItem.Id, OrderItem.DishName).where(OrderItem.Id.in_(last_item_ids))
    ).all()
    names = {int(row[0]): str(row[1]) for row in name_rows}

    return [
        {
            "dishId": int(row[0]),
            "dishName": names.get(int(row[3]), ""),
            "quantity": int(row[1] or 0),
            "amount": fen_to_yuan(int(row[2] or 0)),
        }
        for row in rows
    ]


def get_revenue_stats(
    db: Session,
    range_name: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """计算指定区间的营业额统计。

    Compute the revenue statistics for the requested range.

    :param db: 数据库会话 / database session
    :param range_name: 区间标识 / range identifier
    :param start: 自定义起始日期 / custom start date
    :param end: 自定义结束日期 / custom end date
    :param now: 基准时间，默认当前时间 / base time, defaults to now
    :return: 统计结果字典 / statistics result dict
    :raises ValueError: 区间非法 / when the range is invalid
    """
    span = resolve_range(range_name, start, end, now=now)

    daily_map: Dict[str, Tuple[int, int]] = {
        day_text: (amount_fen, order_count)
        for day_text, amount_fen, order_count in _daily_rows(db, span)
    }

    daily: List[Dict[str, Any]] = []
    total_fen = 0
    total_orders = 0
    cursor = span.start_date
    while cursor <= span.end_date:
        key = cursor.strftime(_DATE_FORMAT)
        amount_fen, order_count = daily_map.get(key, (0, 0))
        total_fen += amount_fen
        total_orders += order_count
        daily.append(
            {"date": key, "amount": fen_to_yuan(amount_fen), "orderCount": order_count}
        )
        cursor += timedelta(days=1)

    average_amount: Optional[str] = None
    if total_orders > 0:
        average_fen = int(
            (Decimal(total_fen) / Decimal(total_orders)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        average_amount = fen_to_yuan(average_fen)

    return {
        "range": span.range_name,
        "startDate": span.start_date.strftime(_DATE_FORMAT),
        "endDate": span.end_date.strftime(_DATE_FORMAT),
        "totalAmount": fen_to_yuan(total_fen),
        "orderCount": total_orders,
        "averageAmount": average_amount,
        "daily": daily,
        "topDishes": _top_dishes(db, span),
    }
