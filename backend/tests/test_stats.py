"""营业统计接口测试。

Tests for the revenue statistics API.
"""

from __future__ import annotations

import itertools
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Category, Dish, Order, OrderItem
from app.services import stats_service

# 订单号自增序列，保证同一测试内订单号唯一
# Monotonic order-number sequence keeping order numbers unique inside a test
_ORDER_SEQ = itertools.count(1)


def test_resolve_range_presets() -> None:
    """预设区间：today / 7d / 30d 的起止与天数。

    Preset ranges: start, end and day count of today / 7d / 30d.
    """
    now = datetime(2026, 11, 3, 15, 30)

    today = stats_service.resolve_range("today", now=now)
    assert today.start_date.isoformat() == "2026-11-03"
    assert today.end_date.isoformat() == "2026-11-03"
    assert today.start == datetime(2026, 11, 3, 0, 0)
    assert today.end == datetime(2026, 11, 4, 0, 0)
    assert today.days == 1

    week = stats_service.resolve_range("7d", now=now)
    assert week.start_date.isoformat() == "2026-10-28"
    assert week.end_date.isoformat() == "2026-11-03"
    assert week.days == 7

    month = stats_service.resolve_range("30d", now=now)
    assert month.start_date.isoformat() == "2026-10-05"
    assert month.end_date.isoformat() == "2026-11-03"
    assert month.days == 30


def test_resolve_range_defaults_to_today() -> None:
    """未传区间时默认 today。

    An empty range falls back to today.
    """
    span = stats_service.resolve_range("", now=datetime(2026, 11, 3, 9, 0))
    assert span.range_name == "today"
    assert span.days == 1


def test_resolve_range_custom() -> None:
    """自定义区间：左闭右开、天数含首尾。

    Custom range: left-closed right-open, day count inclusive of both ends.
    """
    span = stats_service.resolve_range("custom", "2026-09-01", "2026-10-31")
    assert span.range_name == "custom"
    assert span.start_date.isoformat() == "2026-09-01"
    assert span.end_date.isoformat() == "2026-10-31"
    assert span.start == datetime(2026, 9, 1, 0, 0)
    assert span.end == datetime(2026, 11, 1, 0, 0)
    assert span.days == 61


def test_resolve_range_custom_ignores_preset_dates() -> None:
    """预设区间下传入的 start/end 被忽略。

    start/end are ignored for preset ranges.
    """
    now = datetime(2026, 11, 3, 12, 0)
    span = stats_service.resolve_range("7d", "2020-01-01", "2020-01-02", now=now)
    assert span.start_date.isoformat() == "2026-10-28"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"range_name": "foo"},
        {"range_name": "custom"},
        {"range_name": "custom", "start": "2026-09-01"},
        {"range_name": "custom", "start": "2026-09-01", "end": ""},
        {"range_name": "custom", "start": "bad", "end": "2026-10-31"},
        {"range_name": "custom", "start": "2026-10-31", "end": "2026-09-01"},
        {"range_name": "custom", "start": "2025-01-01", "end": "2026-11-01"},
    ],
)
def test_resolve_range_invalid(kwargs: dict) -> None:
    """非法区间与非法日期一律抛 ValueError。

    Invalid ranges and dates always raise ValueError.
    """
    with pytest.raises(ValueError):
        stats_service.resolve_range(**kwargs)


def _ensure_category(db_session):
    """确保存在一个分类，返回该分类。

    Make sure a category exists and return it.

    ``db_session`` 夹具只建表不播种，因此测试必须自己准备分类。
    The ``db_session`` fixture only creates tables without seeding, so tests must
    prepare their own category.

    :param db_session: 数据库会话 / database session
    :return: 分类对象 / category object
    """
    db_session.commit()
    category = db_session.scalars(select(Category).order_by(Category.Id)).first()
    if category is None:
        category = Category(Name="测试分类", SortOrder=0, IsActive=True)
        db_session.add(category)
        db_session.commit()
    return category


def _ensure_dishes(db_session, count: int = 2) -> list:
    """确保存在 ``count`` 个启用中的菜品，返回其 ID（按 ID 排序）。

    Ensure at least ``count`` active dishes exist and return their ids ordered by id.

    :param db_session: 数据库会话 / database session
    :param count: 需要的数量 / required count
    :return: 菜品 ID 列表 / list of dish ids
    """
    db_session.commit()
    dishes = list(db_session.scalars(select(Dish).order_by(Dish.Id)).all())
    active_ids = [dish.Id for dish in dishes if dish.IsActive]
    if len(active_ids) >= count:
        return active_ids[:count]

    category = _ensure_category(db_session)
    while len(active_ids) < count:
        dish = Dish(
            CategoryId=category.Id,
            Name=f"测试菜{len(active_ids) + 1}",
            Price=1000,
            Unit="份",
        )
        db_session.add(dish)
        db_session.commit()
        active_ids.append(dish.Id)
    return active_ids


def _add_dish(db_session, name: str, price_fen: int = 1000) -> int:
    """直接写入一个菜品，返回其 ID。

    Insert a dish directly and return its id.

    :param db_session: 数据库会话 / database session
    :param name: 菜品名称 / dish name
    :param price_fen: 单价（分）/ unit price in fen
    :return: 菜品 ID / dish id
    """
    category = _ensure_category(db_session)
    dish = Dish(CategoryId=category.Id, Name=name, Price=price_fen, Unit="份")
    db_session.add(dish)
    db_session.commit()
    return dish.Id


def _add_order(
    db_session,
    dish_id: int,
    total_fen: int,
    created: datetime,
    status: str = "settled",
    dish_name: str = "测试菜",
    quantity: int = 1,
    unit_price_fen: int = 1000,
) -> Order:
    """直接写入一条订单（含一条明细），用于精确控制统计输入。

    Insert one order with a single item to control the statistics input exactly.

    :param db_session: 数据库会话 / database session
    :param dish_id: 菜品 ID / dish id
    :param total_fen: 订单总金额（分）/ total amount in fen
    :param created: 创建时间 / created time
    :param status: 订单状态 / order status
    :param dish_name: 菜品名称快照 / dish name snapshot
    :param quantity: 数量 / quantity
    :param unit_price_fen: 单价（分）/ unit price in fen
    :return: 订单对象 / the order object
    """
    order = Order(
        OrderNo=f"T{next(_ORDER_SEQ):08d}",
        TableNo="A1",
        DiningType="dine_in",
        Status=status,
        TotalAmount=total_fen,
        CreatedTime=created,
        UpdatedTime=created,
    )
    order.items.append(
        OrderItem(
            DishId=dish_id,
            DishName=dish_name,
            Price=unit_price_fen,
            Quantity=quantity,
            Status="completed",
        )
    )
    db_session.add(order)
    db_session.commit()
    return order


def test_stats_empty_database(db_session) -> None:
    """空库：金额为 0、客单价为 None、趋势全为 0、排行为空。

    Empty database: zero amount, null average, all-zero trend, empty ranking.
    """
    now = datetime(2026, 11, 3, 12, 0)
    stats = stats_service.get_revenue_stats(db_session, "today", now=now)
    assert stats["range"] == "today"
    assert stats["totalAmount"] == "0.00"
    assert stats["orderCount"] == 0
    assert stats["averageAmount"] is None
    assert len(stats["daily"]) == 1
    assert stats["daily"][0]["amount"] == "0.00"
    assert stats["daily"][0]["orderCount"] == 0
    assert stats["topDishes"] == []


def test_stats_counts_only_settled(db_session) -> None:
    """只有已结账订单计入统计。

    Only settled orders are counted.
    """
    dish_id = _ensure_dishes(db_session, 1)[0]
    now = datetime(2026, 11, 3, 12, 0)
    _add_order(db_session, dish_id, 1000, now, status="settled")
    _add_order(db_session, dish_id, 2000, now, status="pending")
    _add_order(db_session, dish_id, 4000, now, status="cooking")
    _add_order(db_session, dish_id, 8000, now, status="completed")
    _add_order(db_session, dish_id, 16000, now, status="cancelled")

    stats = stats_service.get_revenue_stats(db_session, "today", now=now)
    assert stats["totalAmount"] == "10.00"
    assert stats["orderCount"] == 1
    assert stats["averageAmount"] == "10.00"


def test_stats_sums_without_float_error(db_session) -> None:
    """金额按分整数累加，无浮点误差。

    Amounts are summed as integer fen, with no float error.
    """
    dish_id = _ensure_dishes(db_session, 1)[0]
    now = datetime(2026, 11, 3, 12, 0)
    for _ in range(3):
        _add_order(db_session, dish_id, 3333, now)
    stats = stats_service.get_revenue_stats(db_session, "today", now=now)
    assert stats["totalAmount"] == "99.99"
    assert stats["orderCount"] == 3
    assert stats["averageAmount"] == "33.33"


def test_stats_average_rounds_half_up(db_session) -> None:
    """客单价按四舍五入取整（2001/2 = 1000.5 分 -> 1001 分）。

    Average order value rounds half up (2001/2 = 1000.5 fen -> 1001 fen).
    """
    dish_id = _ensure_dishes(db_session, 1)[0]
    now = datetime(2026, 11, 3, 12, 0)
    _add_order(db_session, dish_id, 1000, now)
    _add_order(db_session, dish_id, 1001, now)
    stats = stats_service.get_revenue_stats(db_session, "today", now=now)
    assert stats["totalAmount"] == "20.01"
    assert stats["orderCount"] == 2
    assert stats["averageAmount"] == "10.01"


def test_stats_daily_fills_missing_days(db_session) -> None:
    """区间内没有订单的日期补 0.00，不出现缺项。

    Days without orders are filled with 0.00, never omitted.
    """
    dish_id = _ensure_dishes(db_session, 1)[0]
    now = datetime(2026, 11, 3, 12, 0)
    _add_order(db_session, dish_id, 1234, datetime(2026, 11, 1, 9, 0))

    stats = stats_service.get_revenue_stats(db_session, "7d", now=now)
    assert len(stats["daily"]) == 7
    assert stats["daily"][0]["date"] == "2026-10-28"
    assert stats["daily"][0]["amount"] == "0.00"
    assert stats["daily"][4]["date"] == "2026-11-01"
    assert stats["daily"][4]["amount"] == "12.34"
    assert stats["daily"][4]["orderCount"] == 1
    assert stats["daily"][6]["date"] == "2026-11-03"
    assert stats["daily"][6]["amount"] == "0.00"
    assert stats["totalAmount"] == "12.34"


def test_stats_custom_range_boundaries(db_session) -> None:
    """自定义区间两端都含当天，区间外的订单被排除。

    Both custom-range ends are inclusive; orders outside are excluded.
    """
    dish_id = _ensure_dishes(db_session, 1)[0]
    _add_order(db_session, dish_id, 500, datetime(2026, 10, 1, 0, 0, 0))
    _add_order(db_session, dish_id, 700, datetime(2026, 10, 5, 23, 59, 59))
    _add_order(db_session, dish_id, 900, datetime(2026, 9, 30, 23, 59, 59))
    _add_order(db_session, dish_id, 1100, datetime(2026, 10, 6, 0, 0, 0))

    stats = stats_service.get_revenue_stats(
        db_session, "custom", "2026-10-01", "2026-10-05"
    )
    assert stats["range"] == "custom"
    assert stats["startDate"] == "2026-10-01"
    assert stats["endDate"] == "2026-10-05"
    assert stats["totalAmount"] == "12.00"
    assert stats["orderCount"] == 2
    assert len(stats["daily"]) == 5


def test_stats_top_dishes_merges_renamed_dish(db_session) -> None:
    """同一菜品改名后按 DishId 合并，展示名为最新快照。

    A renamed dish is merged by DishId and shown with its latest snapshot name.
    """
    dish_ids = _ensure_dishes(db_session, 2)
    now = datetime(2026, 11, 3, 12, 0)
    _add_order(
        db_session, dish_ids[0], 1000, now, dish_name="宫保鸡丁", quantity=1, unit_price_fen=1000
    )
    _add_order(
        db_session,
        dish_ids[0],
        2000,
        now,
        dish_name="宫保鸡丁（大份）",
        quantity=2,
        unit_price_fen=1000,
    )
    _add_order(
        db_session, dish_ids[1], 6000, now, dish_name="米饭", quantity=3, unit_price_fen=2000
    )

    stats = stats_service.get_revenue_stats(db_session, "today", now=now)
    top = stats["topDishes"]
    assert [row["dishId"] for row in top] == [dish_ids[1], dish_ids[0]]
    assert top[0]["dishName"] == "米饭"
    assert top[0]["quantity"] == 3
    assert top[0]["amount"] == "60.00"
    assert top[1]["dishName"] == "宫保鸡丁（大份）"
    assert top[1]["quantity"] == 3
    assert top[1]["amount"] == "30.00"


def test_stats_top_dishes_limited_and_sorted(db_session) -> None:
    """排行按金额降序、只保留前 10 条。

    The ranking is sorted by amount descending and capped at 10 rows.
    """
    now = datetime(2026, 11, 3, 12, 0)
    for index in range(12):
        dish_id = _add_dish(db_session, f"菜{index}", price_fen=(index + 1) * 100)
        _add_order(
            db_session,
            dish_id,
            (index + 1) * 100,
            now,
            dish_name=f"菜{index}",
            quantity=1,
            unit_price_fen=(index + 1) * 100,
        )

    stats = stats_service.get_revenue_stats(db_session, "today", now=now)
    top = stats["topDishes"]
    assert len(top) == 10
    amounts = [float(row["amount"]) for row in top]
    assert amounts == sorted(amounts, reverse=True)
    assert top[0]["amount"] == "12.00"
    assert top[-1]["amount"] == "3.00"


def test_stats_ignores_other_days(db_session) -> None:
    """今日统计不含昨天与明天的订单。

    Today's statistics exclude yesterday's and tomorrow's orders.
    """
    dish_id = _ensure_dishes(db_session, 1)[0]
    now = datetime(2026, 11, 3, 12, 0)
    _add_order(db_session, dish_id, 100, datetime(2026, 11, 2, 23, 59, 59))
    _add_order(db_session, dish_id, 200, datetime(2026, 11, 4, 0, 0, 0))
    _add_order(db_session, dish_id, 400, datetime(2026, 11, 3, 0, 0, 0))
    _add_order(db_session, dish_id, 800, datetime(2026, 11, 3, 23, 59, 59))

    stats = stats_service.get_revenue_stats(db_session, "today", now=now)
    assert stats["totalAmount"] == "12.00"
    assert stats["orderCount"] == 2


def test_revenue_endpoint_default_today(client: TestClient) -> None:
    """GET /api/stats/revenue 默认区间为 today，空库也能正常返回。

    GET /api/stats/revenue defaults to today and works on an empty database.
    """
    resp = client.get("/api/stats/revenue")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["range"] == "today"
    assert body["totalAmount"] == "0.00"
    assert body["orderCount"] == 0
    assert body["averageAmount"] is None
    assert len(body["daily"]) == 1
    assert body["topDishes"] == []


def test_revenue_endpoint_preset_lengths(client: TestClient) -> None:
    """7d / 30d 区间返回对应天数。

    The 7d / 30d ranges return the matching number of days.
    """
    for preset, expected_days in (("7d", 7), ("30d", 30)):
        resp = client.get("/api/stats/revenue", params={"range": preset})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["range"] == preset
        assert len(body["daily"]) == expected_days


def test_revenue_endpoint_custom_range(client: TestClient, db_session) -> None:
    """自定义区间返回请求中的起止日期。

    A custom range returns the requested start and end dates.
    """
    dish_id = _ensure_dishes(db_session, 1)[0]
    _add_order(db_session, dish_id, 2500, datetime(2026, 10, 5, 12, 0))

    resp = client.get(
        "/api/stats/revenue",
        params={"range": "custom", "start": "2026-10-01", "end": "2026-10-05"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["range"] == "custom"
    assert body["startDate"] == "2026-10-01"
    assert body["endDate"] == "2026-10-05"
    assert body["totalAmount"] == "25.00"
    assert len(body["daily"]) == 5


def test_revenue_endpoint_ignores_dates_on_preset(client: TestClient) -> None:
    """预设区间下传入 start/end 被忽略。

    start/end are ignored for preset ranges.
    """
    resp = client.get(
        "/api/stats/revenue",
        params={"range": "7d", "start": "2020-01-01", "end": "2020-01-02"},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["daily"]) == 7


@pytest.mark.parametrize(
    "params",
    [
        {"range": "foo"},
        {"range": "custom"},
        {"range": "custom", "start": "2026-10-01"},
        {"range": "custom", "start": "bad", "end": "2026-10-05"},
        {"range": "custom", "start": "2026-10-05", "end": "2026-10-01"},
        {"range": "custom", "start": "2025-01-01", "end": "2026-11-01"},
    ],
)
def test_revenue_endpoint_invalid_params(client: TestClient, params: dict) -> None:
    """非法区间与非法日期返回 400。

    Invalid ranges and dates return 400.
    """
    resp = client.get("/api/stats/revenue", params=params)
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]
