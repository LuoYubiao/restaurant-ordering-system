"""订单接口路由。

Order API router.

提供下单、订单查询、状态流转、明细出餐与补打接口。
Provides endpoints for creating orders, querying orders, transitioning statuses,
serving items and reprinting tickets.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.order import (
    OrderCreate,
    OrderCreateResult,
    OrderItemStatusUpdate,
    OrderOut,
    OrderStatusUpdate,
    PrintRequest,
    PrintResult as PrintResultSchema,
)
from ..services import order_service, printer_service

logger = logging.getLogger(__name__)

# 订单接口路由 / Order router
router = APIRouter(tags=["orders"])

# 打印目标：柜台单 / Print target: counter ticket
_PRINT_TARGET_COUNTER = "counter"
# 打印目标：厨房单 / Print target: kitchen ticket
_PRINT_TARGET_KITCHEN = "kitchen"
# 打印目标：两者 / Print target: both
_PRINT_TARGET_BOTH = "both"


def _to_http_error(exc: order_service.BusinessError) -> HTTPException:
    """把业务异常转换为 HTTP 异常。

    Convert a business error into an HTTP exception.

    :param exc: 业务异常 / business error
    :return: HTTP 异常 / HTTP exception
    """
    return HTTPException(status_code=exc.http_status, detail=exc.message)


def _resolve_targets(target: str) -> List[str]:
    """把打印目标解析为打印机服务可识别的列表。

    Resolve a print target into a list understood by the printer service.

    :param target: counter / kitchen / both
    :return: 目标列表 / target list
    :raises order_service.BusinessError: 未知目标 / unknown target
    """
    normalized = (target or _PRINT_TARGET_BOTH).lower()
    if normalized == _PRINT_TARGET_COUNTER:
        return [_PRINT_TARGET_COUNTER]
    if normalized == _PRINT_TARGET_KITCHEN:
        return [_PRINT_TARGET_KITCHEN]
    if normalized == _PRINT_TARGET_BOTH:
        return [_PRINT_TARGET_COUNTER, _PRINT_TARGET_KITCHEN]
    raise order_service.BusinessError(f"未知打印目标：{target}")


def _print_results_to_dicts(results: List[printer_service.PrintResult]) -> List[dict]:
    """把打印机结果数据类转换为可序列化字典。

    Convert printer result dataclasses into serializable dicts.

    :param results: 打印结果列表 / list of print results
    :return: 字典列表 / list of dicts
    """
    return [
        {"target": result.target, "ok": result.ok, "message": result.message}
        for result in results
    ]


@router.post("/orders", response_model=OrderCreateResult, status_code=201)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)) -> dict:
    """创建订单并按配置自动打印小票。

    Create an order and auto-print tickets according to configuration.

    打印失败不会导致下单失败，失败信息会放入 ``printResults``。
    Printing failures never fail the order; the failure reason is returned in
    ``printResults``.

    :param payload: 下单输入 / order creation input
    :param db: 数据库会话 / database session
    :return: 订单详情与打印结果 / order detail and print results
    """
    try:
        order = order_service.create_order(db, payload)
    except order_service.BusinessError as exc:
        raise _to_http_error(exc)

    order_view = order_service.to_order_out(order)

    print_results: List[dict] = []
    try:
        results = printer_service.print_order(order_view, targets=None)
        print_results = _print_results_to_dicts(results)
    except Exception as exc:  # noqa: BLE001 - printing must never fail ordering
        logger.error("Order printing failed, orderNo=%s error=%s", order.OrderNo, exc)
        print_results = [
            {"target": "unknown", "ok": False, "message": f"打印失败：{exc}"}
        ]

    return {"order": order_view, "printResults": print_results}


@router.get("/orders", response_model=List[OrderOut])
def list_orders(
    status: Optional[str] = Query(default=None),
    date: Optional[str] = Query(default=None),
    limit: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> List[dict]:
    """查询订单列表（按创建时间倒序）。

    List orders ordered by creation time descending.

    :param status: 状态过滤，支持逗号分隔多值 / status filter, comma-separated
    :param date: 日期过滤（``YYYY-MM-DD``）/ date filter (``YYYY-MM-DD``)
    :param limit: 返回条数上限 / max number of orders to return
    :param db: 数据库会话 / database session
    :return: 订单视图列表 / list of order views
    """
    try:
        orders = order_service.list_orders(db, status=status, date=date)
    except order_service.BusinessError as exc:
        raise _to_http_error(exc)

    if limit is not None:
        orders = orders[:limit]
    return [order_service.to_order_out(order) for order in orders]


@router.get("/orders/{order_id:int}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)) -> dict:
    """获取单个订单详情。

    Get a single order detail.

    :param order_id: 订单 ID / order id
    :param db: 数据库会话 / database session
    :return: 订单视图 / order view
    """
    try:
        order = order_service.get_order(db, order_id)
    except order_service.BusinessError as exc:
        raise _to_http_error(exc)
    return order_service.to_order_out(order)


@router.patch("/orders/{order_id:int}/status", response_model=OrderOut)
def update_order_status(
    order_id: int, payload: OrderStatusUpdate, db: Session = Depends(get_db)
) -> dict:
    """更新订单状态。

    Update the order status.

    :param order_id: 订单 ID / order id
    :param payload: 目标状态 / target status
    :param db: 数据库会话 / database session
    :return: 订单视图 / order view
    """
    try:
        order = order_service.get_order(db, order_id)
        order = order_service.update_order_status(db, order, payload.status)
    except order_service.BusinessError as exc:
        raise _to_http_error(exc)
    return order_service.to_order_out(order)


@router.patch("/orders/{order_id:int}/items/{item_id:int}/status", response_model=OrderOut)
def update_item_status(
    order_id: int,
    item_id: int,
    payload: OrderItemStatusUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """更新单条明细状态（支持出餐与撤销）。

    Update a single item status (serving and undo both supported).

    :param order_id: 订单 ID / order id
    :param item_id: 明细 ID / item id
    :param payload: 目标状态（pending / completed）/ target status
    :param db: 数据库会话 / database session
    :return: 订单视图 / order view
    """
    try:
        order = order_service.get_order(db, order_id)
        order = order_service.update_item_status(db, order, item_id, payload.status)
    except order_service.BusinessError as exc:
        raise _to_http_error(exc)
    return order_service.to_order_out(order)


@router.patch("/orders/{order_id:int}/items/complete-all", response_model=OrderOut)
def complete_all_items(order_id: int, db: Session = Depends(get_db)) -> dict:
    """把订单下所有明细一次性标为出餐完成。

    Mark all items of the order as completed at once.

    :param order_id: 订单 ID / order id
    :param db: 数据库会话 / database session
    :return: 订单视图 / order view
    """
    try:
        order = order_service.get_order(db, order_id)
        order = order_service.complete_all_items(db, order)
    except order_service.BusinessError as exc:
        raise _to_http_error(exc)
    return order_service.to_order_out(order)


@router.post("/orders/{order_id:int}/print", response_model=List[PrintResultSchema])
def reprint_order(
    order_id: int, payload: PrintRequest, db: Session = Depends(get_db)
) -> List[dict]:
    """手动补打小票（累计打印次数）。

    Manually reprint tickets (incrementing the print count).

    :param order_id: 订单 ID / order id
    :param payload: 打印目标（counter / kitchen / both）/ print target
    :param db: 数据库会话 / database session
    :return: 打印结果列表 / list of print results
    """
    try:
        targets = _resolve_targets(payload.target)
        order = order_service.get_order(db, order_id)
    except order_service.BusinessError as exc:
        raise _to_http_error(exc)

    # 累计打印次数 / Increment the print count
    order.PrintCount += 1
    db.commit()
    db.refresh(order)

    order_view = order_service.to_order_out(order)
    try:
        results = printer_service.print_order(order_view, targets=targets)
    except Exception as exc:  # noqa: BLE001 - printing must never fail the request
        logger.error("Order reprint failed, orderNo=%s error=%s", order.OrderNo, exc)
        return [
            {"target": target, "ok": False, "message": f"打印失败：{exc}"}
            for target in targets
        ]
    return _print_results_to_dicts(results)
