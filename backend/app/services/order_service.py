"""订单业务服务模块。

Order business service module.

集中存放订单相关业务逻辑（下单、查询、状态流转与明细出餐），供 API 层调用。
所有金额以「分」为单位的整数存储与计算，对外统一返回保留两位小数的字符串。
All order-related business logic (creation, query, status transitions and item
serving) lives here so the API layer stays thin. Amounts are stored/computed as
integers in fen and exposed as 2-decimal strings.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    DINING_TYPE_TEXT,
    ORDER_ITEM_STATUS_TEXT,
    ORDER_STATUS_TEXT,
    Dish,
    DiningType,
    Order,
    OrderItem,
    OrderItemStatus,
    OrderStatus,
)
from ..money import fen_to_yuan
from ..schemas.order import OrderCreate
from . import event_bus

logger = logging.getLogger(__name__)

# 订单合法状态跳转表 / Allowed order status transition table
_ALLOWED_ORDER_TRANSITIONS: Dict[str, set] = {
    OrderStatus.PENDING.value: {OrderStatus.COOKING.value, OrderStatus.CANCELLED.value},
    OrderStatus.COOKING.value: {OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value},
    OrderStatus.COMPLETED.value: {OrderStatus.SETTLED.value, OrderStatus.CANCELLED.value},
    OrderStatus.SETTLED.value: {OrderStatus.CANCELLED.value},
    OrderStatus.CANCELLED.value: set(),
}


class BusinessError(Exception):
    """业务异常，携带中文提示与对应 HTTP 状态码。

    Business exception carrying a Chinese message and an HTTP status code. The
    API layer converts it into an ``HTTPException``.
    """

    def __init__(self, message: str, http_status: int = 400) -> None:
        """构造业务异常。

        Build a business exception.

        :param message: 中文错误提示 / Chinese error message
        :param http_status: 对应 HTTP 状态码 / corresponding HTTP status code
        """
        super().__init__(message)
        # 中文错误提示 / Chinese error message
        self.message = message
        # 对应 HTTP 状态码 / Corresponding HTTP status code
        self.http_status = http_status


def _iso(value: Optional[datetime]) -> Optional[str]:
    """把时间对象格式化为 ISO 字符串。

    Format a datetime value into an ISO string.

    :param value: 时间对象或 None / datetime value or None
    :return: ISO 字符串或 None / ISO string or None
    """
    return value.isoformat() if value is not None else None


def _order_status_text(status: str) -> str:
    """返回订单状态中文文案。

    Return the Chinese text of an order status.

    :param status: 订单状态值 / order status value
    :return: 中文文案 / Chinese text
    """
    return ORDER_STATUS_TEXT.get(status, status)


def build_order_no(db: Session) -> str:
    """生成订单号（``YYYYMMDD-NNNN``，当天 4 位序号）。

    Build an order number (``YYYYMMDD-NNNN``, a 4-digit daily sequence).

    :param db: 数据库会话 / database session
    :return: 唯一订单号 / unique order number
    """
    prefix = datetime.now().strftime("%Y%m%d")
    existing = db.scalars(
        select(Order.OrderNo).where(Order.OrderNo.like(f"{prefix}-%"))
    ).all()
    max_seq = 0
    for order_no in existing:
        suffix = order_no.rsplit("-", 1)[-1]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    order_no = f"{prefix}-{max_seq + 1:04d}"
    logger.debug("Generated order number: %s", order_no)
    return order_no


def to_order_out(order: Order) -> Dict[str, Any]:
    """把订单 ORM 对象转换为与 ``OrderOut`` 一致的字典。

    Convert an order ORM object into a dict matching ``OrderOut``.

    该函数是打印与 SSE 的共同数据源，必须保持唯一。
    This function is the single shared data source for printing and SSE.

    :param order: 订单 ORM 对象 / order ORM object
    :return: 与 ``OrderOut`` 结构一致的字典 / dict matching ``OrderOut``
    """
    items: List[Dict[str, Any]] = []
    completed_count = 0
    for item in order.items:
        if item.Status == OrderItemStatus.COMPLETED.value:
            completed_count += 1
        items.append(
            {
                "id": item.Id,
                "dishId": item.DishId,
                "dishName": item.DishName,
                "price": fen_to_yuan(item.Price),
                "quantity": item.Quantity,
                "remark": item.Remark,
                "status": item.Status,
                "statusText": ORDER_ITEM_STATUS_TEXT.get(item.Status, item.Status),
                "completedTime": _iso(item.CompletedTime),
            }
        )
    return {
        "id": order.Id,
        "orderNo": order.OrderNo,
        "tableNo": order.TableNo,
        "diningType": order.DiningType,
        "diningTypeText": DINING_TYPE_TEXT.get(order.DiningType, order.DiningType),
        "status": order.Status,
        "statusText": _order_status_text(order.Status),
        "totalAmount": fen_to_yuan(order.TotalAmount),
        "remark": order.Remark,
        "printCount": order.PrintCount,
        "itemCount": len(items),
        "completedCount": completed_count,
        "createdTime": _iso(order.CreatedTime),
        "updatedTime": _iso(order.UpdatedTime),
        "items": items,
    }


def _load_dishes(db: Session, dish_ids: List[int]) -> Dict[int, Dish]:
    """按 ID 批量加载菜品。

    Load dishes in batch by their ids.

    :param db: 数据库会话 / database session
    :param dish_ids: 菜品 ID 列表 / list of dish ids
    :return: {菜品ID: 菜品} 映射 / mapping of dish id to dish
    """
    if not dish_ids:
        return {}
    dishes = db.scalars(select(Dish).where(Dish.Id.in_(dish_ids))).all()
    return {dish.Id: dish for dish in dishes}


def create_order(db: Session, payload: OrderCreate) -> Order:
    """创建订单（落库、快照菜品与单价、服务端重算金额）。

    Create an order: persist it, snapshot dish names/prices and recompute the
    total amount on the server side.

    :param db: 数据库会话 / database session
    :param payload: 下单输入 / order creation input
    :return: 新建的订单 ORM 对象 / the created order ORM object
    :raises BusinessError: 明细为空或菜品不可用 / empty items or unavailable dish
    """
    if not payload.items:
        raise BusinessError("下单失败：订单明细不能为空")

    dishes = _load_dishes(db, [item.dishId for item in payload.items])

    total_amount = 0
    order = Order(
        OrderNo=build_order_no(db),
        TableNo=payload.tableNo,
        DiningType=payload.diningType or DiningType.DINE_IN.value,
        Status=OrderStatus.PENDING.value,
        TotalAmount=0,
        Remark=payload.remark,
        PrintCount=0,
        CreatedTime=datetime.now(),
        UpdatedTime=datetime.now(),
    )

    for item_in in payload.items:
        dish = dishes.get(item_in.dishId)
        if dish is None or not dish.IsActive:
            name = dish.Name if dish is not None else f"ID={item_in.dishId}"
            raise BusinessError(f"菜品 {name} 已下架，无法下单")
        # 快照菜名与单价，后续改菜价不影响历史订单
        # Snapshot the dish name and price so later price changes do not affect
        # historical orders
        order.items.append(
            OrderItem(
                DishId=dish.Id,
                DishName=dish.Name,
                Price=dish.Price,
                Quantity=item_in.quantity,
                Remark=item_in.remark,
                Status=OrderItemStatus.PENDING.value,
            )
        )
        total_amount += dish.Price * item_in.quantity

    # 金额由服务端重算，忽略客户端传入的 totalAmount
    # Amount recomputed server-side; any client-provided total is ignored
    order.TotalAmount = total_amount

    db.add(order)
    db.commit()
    db.refresh(order)
    logger.info(
        "Order created, orderNo=%s totalAmount=%s items=%s",
        order.OrderNo,
        order.TotalAmount,
        len(order.items),
    )
    event_bus.event_bus.publish(event_bus.EVENT_ORDER_CREATED, to_order_out(order))
    return order


def get_order(db: Session, order_id: int) -> Order:
    """按 ID 获取订单，不存在则抛业务异常。

    Get an order by id, raising a business error when missing.

    :param db: 数据库会话 / database session
    :param order_id: 订单 ID / order id
    :return: 订单 ORM 对象 / order ORM object
    :raises BusinessError: 订单不存在（404）/ order not found (404)
    """
    order = db.get(Order, order_id)
    if order is None:
        raise BusinessError(f"订单不存在：{order_id}", http_status=404)
    return order


def list_orders(
    db: Session,
    status: Optional[str] = None,
    date: Optional[str] = None,
    include_items: bool = True,
) -> List[Order]:
    """查询订单列表（按创建时间倒序）。

    List orders ordered by creation time descending.

    :param db: 数据库会话 / database session
    :param status: 状态过滤，支持逗号分隔多值（如 ``pending,cooking``）
        / status filter, comma-separated multiple values
    :param date: 日期过滤（``YYYY-MM-DD``）/ date filter (``YYYY-MM-DD``)
    :param include_items: 是否预加载明细 / whether to eager-load items
    :return: 订单列表 / list of orders
    :raises BusinessError: 日期格式非法 / invalid date format
    """
    stmt = select(Order)
    if include_items:
        stmt = stmt.options(selectinload(Order.items))

    if status:
        wanted = [value.strip() for value in status.split(",") if value.strip()]
        if wanted:
            stmt = stmt.where(Order.Status.in_(wanted))

    if date:
        try:
            day_start = datetime.strptime(date, "%Y-%m-%d")
        except ValueError as exc:
            raise BusinessError(f"日期格式无效：{date}，应为 YYYY-MM-DD") from exc
        day_end = day_start + timedelta(days=1)
        stmt = stmt.where(Order.CreatedTime >= day_start, Order.CreatedTime < day_end)

    stmt = stmt.order_by(Order.CreatedTime.desc(), Order.Id.desc())
    return list(db.scalars(stmt).all())


def _derive_order_status(order: Order) -> bool:
    """根据明细状态派生订单状态。

    Derive the order status from its item statuses.

    - 全部明细完成 -> 订单置为 ``completed``；
      all items completed -> order becomes ``completed``;
    - 存在未完成明细且订单当前为 ``completed`` -> 回退为 ``cooking``；
      some items incomplete and order is ``completed`` -> revert to ``cooking``;
    - 订单已 ``settled`` / ``cancelled`` 时不参与派生。
      ``settled`` / ``cancelled`` orders are never derived.

    :param order: 订单 ORM 对象 / order ORM object
    :return: 订单状态是否发生变化 / whether the order status changed
    """
    if order.Status in (OrderStatus.SETTLED.value, OrderStatus.CANCELLED.value):
        return False

    items = order.items
    all_completed = bool(items) and all(
        item.Status == OrderItemStatus.COMPLETED.value for item in items
    )
    new_status = order.Status
    if all_completed:
        new_status = OrderStatus.COMPLETED.value
    elif order.Status == OrderStatus.COMPLETED.value:
        new_status = OrderStatus.COOKING.value

    if new_status != order.Status:
        logger.info(
            "Order status derived, orderNo=%s %s -> %s",
            order.OrderNo,
            order.Status,
            new_status,
        )
        order.Status = new_status
        return True
    return False


def update_order_status(db: Session, order: Order, new_status: str) -> Order:
    """更新订单状态（校验状态机）。

    Update the order status, validating the state machine.

    :param db: 数据库会话 / database session
    :param order: 订单 ORM 对象 / order ORM object
    :param new_status: 目标状态 / target status
    :return: 更新后的订单 / updated order
    :raises BusinessError: 非法状态跳转（400）/ illegal transition (400)
    """
    valid_statuses = {member.value for member in OrderStatus}
    if new_status not in valid_statuses:
        raise BusinessError(f"非法的订单状态：{new_status}")

    allowed = _ALLOWED_ORDER_TRANSITIONS.get(order.Status, set())
    if new_status not in allowed:
        raise BusinessError(
            f"订单当前状态为{_order_status_text(order.Status)}，"
            f"不能变更为{_order_status_text(new_status)}"
        )

    previous = order.Status
    order.Status = new_status
    order.UpdatedTime = datetime.now()
    db.commit()
    db.refresh(order)
    logger.info("Order status updated, orderNo=%s %s -> %s", order.OrderNo, previous, new_status)
    event_bus.event_bus.publish(
        event_bus.EVENT_ORDER_STATUS_CHANGED, to_order_out(order)
    )
    return order


def _find_item(order: Order, item_id: int) -> OrderItem:
    """在订单中查找指定明细。

    Find a specific item inside the order.

    :param order: 订单 ORM 对象 / order ORM object
    :param item_id: 明细 ID / item id
    :return: 明细 ORM 对象 / item ORM object
    :raises BusinessError: 明细不存在（404）/ item not found (404)
    """
    for item in order.items:
        if item.Id == item_id:
            return item
    raise BusinessError(f"订单明细不存在：{item_id}", http_status=404)


def _apply_item_status(item: OrderItem, new_status: str) -> None:
    """应用明细状态变更并维护完成时间。

    Apply an item status change and maintain its completion time.

    :param item: 明细 ORM 对象 / item ORM object
    :param new_status: 目标状态（pending / completed）/ target status
    """
    item.Status = new_status
    if new_status == OrderItemStatus.COMPLETED.value:
        item.CompletedTime = datetime.now()
    else:
        item.CompletedTime = None


def update_item_status(
    db: Session, order: Order, item_id: int, new_status: str
) -> Order:
    """更新单条明细状态并派生订单状态。

    Update a single item status and derive the order status.

    :param db: 数据库会话 / database session
    :param order: 订单 ORM 对象 / order ORM object
    :param item_id: 明细 ID / item id
    :param new_status: 目标状态（pending / completed）/ target status
    :return: 更新后的订单 / updated order
    :raises BusinessError: 明细状态非法或明细不存在 / invalid item status or missing item
    """
    if new_status not in (
        OrderItemStatus.PENDING.value,
        OrderItemStatus.COMPLETED.value,
    ):
        raise BusinessError(f"非法的明细状态：{new_status}")

    item = _find_item(order, item_id)
    _apply_item_status(item, new_status)
    order.UpdatedTime = datetime.now()
    status_changed = _derive_order_status(order)
    db.commit()
    db.refresh(order)
    logger.info(
        "Order item status updated, orderNo=%s itemId=%s -> %s",
        order.OrderNo,
        item_id,
        new_status,
    )
    view = to_order_out(order)
    event_bus.event_bus.publish(event_bus.EVENT_ORDER_ITEM_STATUS_CHANGED, view)
    if status_changed:
        event_bus.event_bus.publish(event_bus.EVENT_ORDER_STATUS_CHANGED, view)
    return order


def complete_all_items(db: Session, order: Order) -> Order:
    """把订单下所有待出餐明细一次性置为已完成并派生订单状态。

    Mark every pending item of the order as completed at once, then derive the
    order status.

    :param db: 数据库会话 / database session
    :param order: 订单 ORM 对象 / order ORM object
    :return: 更新后的订单 / updated order
    """
    now = datetime.now()
    for item in order.items:
        if item.Status != OrderItemStatus.COMPLETED.value:
            item.Status = OrderItemStatus.COMPLETED.value
            item.CompletedTime = now
    order.UpdatedTime = now
    status_changed = _derive_order_status(order)
    db.commit()
    db.refresh(order)
    logger.info("All order items completed, orderNo=%s", order.OrderNo)
    view = to_order_out(order)
    event_bus.event_bus.publish(event_bus.EVENT_ORDER_ITEM_STATUS_CHANGED, view)
    if status_changed:
        event_bus.event_bus.publish(event_bus.EVENT_ORDER_STATUS_CHANGED, view)
    return order


# 对外导出清单 / Public export list
__all__ = [
    "BusinessError",
    "build_order_no",
    "to_order_out",
    "create_order",
    "get_order",
    "list_orders",
    "update_order_status",
    "update_item_status",
    "complete_all_items",
]
