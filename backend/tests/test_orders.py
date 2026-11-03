"""订单接口测试。

Tests for the order API.

覆盖下单、金额重算、软删除校验、状态机、逐道菜出餐、撤销、批量出餐、
取消、补打与模拟打印等场景。
Covers order creation, amount recomputation, soft-delete validation, the status
machine, per-item serving, undo, bulk serving, cancellation, reprint and mock
printing.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models import Dish, Order


def _active_dishes(db_session, count: int = 1) -> list:
    """获取若干启用中的菜品（按 ID 排序）。

    Fetch several active dishes ordered by id.

    :param db_session: 数据库会话 / database session
    :param count: 需要的数量 / required count
    :return: 菜品列表 / list of dishes
    """
    # 结束可能存在的读事务，获取最新快照
    # End any open read transaction to get a fresh snapshot
    db_session.commit()
    dishes = list(db_session.scalars(select(Dish).order_by(Dish.Id)).all())
    active = [dish for dish in dishes if dish.IsActive]
    return active[:count]


def _order_count(db_session) -> int:
    """统计订单总数（使用最新快照）。

    Count the total number of orders (using a fresh snapshot).

    :param db_session: 数据库会话 / database session
    :return: 订单数量 / order count
    """
    db_session.commit()
    return db_session.scalar(select(func.count()).select_from(Order))


def _create_order(client: TestClient, dish_ids: list, total: str | None = None):
    """构造下单请求。

    Build and send an order-creation request.

    :param client: 测试客户端 / test client
    :param dish_ids: 菜品 ID 列表 / list of dish ids
    :param total: 可选的客户端总金额 / optional client-provided total
    :return: 响应对象 / response object
    """
    payload = {
        "tableNo": "A1",
        "diningType": "dine_in",
        "remark": "少辣",
        "items": [{"dishId": dish_id, "quantity": 1} for dish_id in dish_ids],
    }
    if total is not None:
        payload["totalAmount"] = total
    return client.post("/api/orders", json=payload)


def _patch_status(client: TestClient, order_id: int, status: str):
    """更新订单状态。

    Update the order status.

    :param client: 测试客户端 / test client
    :param order_id: 订单 ID / order id
    :param status: 目标状态 / target status
    :return: 响应对象 / response object
    """
    return client.patch(f"/api/orders/{order_id}/status", json={"status": status})


def _patch_item_status(client: TestClient, order_id: int, item_id: int, status: str):
    """更新明细状态。

    Update an item status.

    :param client: 测试客户端 / test client
    :param order_id: 订单 ID / order id
    :param item_id: 明细 ID / item id
    :param status: 目标状态 / target status
    :return: 响应对象 / response object
    """
    return client.patch(
        f"/api/orders/{order_id}/items/{item_id}/status", json={"status": status}
    )


def test_create_order_success(client: TestClient, db_session) -> None:
    """成功下单：订单号、状态、明细快照与金额校验。

    Successful order creation: order number, status, item snapshots and amount.
    """
    dish = _active_dishes(db_session, 1)[0]
    resp = _create_order(client, [dish.Id])
    assert resp.status_code == 201

    body = resp.json()
    order = body["order"]

    # 订单号格式 YYYYMMDD-NNNN / Order number format YYYYMMDD-NNNN
    assert re.match(r"^\d{8}-\d{4}$", order["orderNo"])
    assert order["status"] == "pending"
    assert order["statusText"] == "待接单"
    assert order["diningTypeText"] == "堂食"
    assert order["itemCount"] == 1
    assert order["completedCount"] == 0

    item = order["items"][0]
    assert item["dishName"] == dish.Name
    assert item["price"] == f"{dish.Price / 100:.2f}"
    assert item["status"] == "pending"
    assert item["completedTime"] is None

    # 金额 = 单价 × 数量，且为两位小数字符串
    # Amount = unit price × quantity, formatted as a 2-decimal string
    expected = f"{dish.Price * 1 / 100:.2f}"
    assert order["totalAmount"] == expected
    assert len(order["totalAmount"].split(".")[1]) == 2

    # mock 模式下自动打印柜台单与厨房单
    # Mock mode auto-prints the counter and kitchen tickets
    assert [result["target"] for result in body["printResults"]] == [
        "counter",
        "kitchen",
    ]
    assert all(result["ok"] for result in body["printResults"])


def test_create_order_ignores_client_total(client: TestClient, db_session) -> None:
    """客户端传入错误金额时，仍以服务端重算结果为准。

    The client-provided (wrong) total is ignored; the server recomputes it.
    """
    dish = _active_dishes(db_session, 1)[0]
    resp = _create_order(client, [dish.Id], total="0.01")
    assert resp.status_code == 201
    order = resp.json()["order"]
    assert order["totalAmount"] == f"{dish.Price / 100:.2f}"
    assert order["totalAmount"] != "0.01"


def test_create_order_with_inactive_dish(client: TestClient, db_session) -> None:
    """包含已软删除的菜品应返回 400，且不创建订单。

    Ordering a soft-deleted dish returns 400 and does not create an order.
    """
    dish = _active_dishes(db_session, 1)[0]
    dish.IsActive = False
    db_session.commit()

    before = _order_count(db_session)
    resp = _create_order(client, [dish.Id])
    assert resp.status_code == 400
    assert "已下架" in resp.json()["detail"]

    after = _order_count(db_session)
    assert after == before


def test_order_status_machine(client: TestClient, db_session) -> None:
    """订单状态机：合法跳转成功，非法跳转返回 400。

    Order status machine: legal transitions succeed, illegal ones return 400.
    """
    dish = _active_dishes(db_session, 1)[0]

    # 合法链路 pending -> cooking -> completed -> settled -> cancelled
    # Legal chain: pending -> cooking -> completed -> settled -> cancelled
    order_id = _create_order(client, [dish.Id]).json()["order"]["id"]
    assert _patch_status(client, order_id, "cooking").status_code == 200
    assert _patch_status(client, order_id, "completed").json()["status"] == "completed"
    assert _patch_status(client, order_id, "settled").json()["status"] == "settled"
    assert _patch_status(client, order_id, "cancelled").json()["status"] == "cancelled"

    # 非法跳转：pending -> completed
    # Illegal transition: pending -> completed
    order_id = _create_order(client, [dish.Id]).json()["order"]["id"]
    resp = _patch_status(client, order_id, "completed")
    assert resp.status_code == 400
    assert "不能变更" in resp.json()["detail"]

    # 非法跳转：pending -> settled
    # Illegal transition: pending -> settled
    assert _patch_status(client, order_id, "settled").status_code == 400

    # 非法跳转：settled -> cooking
    # Illegal transition: settled -> cooking
    assert _patch_status(client, order_id, "cooking").status_code == 200  # pending -> cooking
    assert _patch_status(client, order_id, "completed").status_code == 200
    assert _patch_status(client, order_id, "settled").status_code == 200
    resp = _patch_status(client, order_id, "cooking")
    assert resp.status_code == 400
    assert "已结账" in resp.json()["detail"]


def test_serve_items_one_by_one(client: TestClient, db_session) -> None:
    """逐道菜出餐：部分完成时订单保持 cooking。

    Serving items one by one: the order stays cooking until all items are done.
    """
    dishes = _active_dishes(db_session, 2)
    order = _create_order(client, [dish.Id for dish in dishes]).json()["order"]
    order_id = order["id"]
    items = order["items"]

    assert _patch_status(client, order_id, "cooking").status_code == 200

    resp = _patch_item_status(client, order_id, items[0]["id"], "completed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cooking"
    assert body["completedCount"] == 1
    assert body["items"][0]["status"] == "completed"
    assert body["items"][0]["completedTime"] is not None
    assert body["items"][1]["status"] == "pending"


def test_order_completed_when_all_items_done(client: TestClient, db_session) -> None:
    """全部明细完成后，订单状态自动变为 completed。

    When all items are completed, the order status auto-becomes completed.
    """
    dishes = _active_dishes(db_session, 2)
    order = _create_order(client, [dish.Id for dish in dishes]).json()["order"]
    order_id = order["id"]
    items = order["items"]

    assert _patch_status(client, order_id, "cooking").status_code == 200
    _patch_item_status(client, order_id, items[0]["id"], "completed")
    resp = _patch_item_status(client, order_id, items[1]["id"], "completed")
    body = resp.json()
    assert body["status"] == "completed"
    assert body["statusText"] == "已出餐"
    assert body["completedCount"] == 2


def test_undo_item_reverts_order_to_cooking(client: TestClient, db_session) -> None:
    """撤销出餐：订单由 completed 回退为 cooking，且清空完成时间。

    Undo serving: the order reverts from completed to cooking and the item's
    completion time is cleared.
    """
    dishes = _active_dishes(db_session, 2)
    order = _create_order(client, [dish.Id for dish in dishes]).json()["order"]
    order_id = order["id"]
    items = order["items"]

    assert _patch_status(client, order_id, "cooking").status_code == 200
    _patch_item_status(client, order_id, items[0]["id"], "completed")
    body = _patch_item_status(client, order_id, items[1]["id"], "completed").json()
    assert body["status"] == "completed"

    resp = _patch_item_status(client, order_id, items[1]["id"], "pending")
    body = resp.json()
    assert body["status"] == "cooking"
    assert body["completedCount"] == 1
    assert body["items"][1]["status"] == "pending"
    assert body["items"][1]["completedTime"] is None


def test_complete_all_items(client: TestClient, db_session) -> None:
    """批量出餐后订单为 completed，且所有明细均完成。

    Bulk serving marks all items completed and the order becomes completed.
    """
    dishes = _active_dishes(db_session, 3)
    order = _create_order(client, [dish.Id for dish in dishes]).json()["order"]
    order_id = order["id"]

    assert _patch_status(client, order_id, "cooking").status_code == 200
    resp = client.patch(f"/api/orders/{order_id}/items/complete-all")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["completedCount"] == 3
    assert all(item["status"] == "completed" for item in body["items"])
    assert all(item["completedTime"] is not None for item in body["items"])


def test_cancel_order_keeps_item_status(client: TestClient, db_session) -> None:
    """取消订单不修改任何明细状态。

    Cancelling an order does not modify item statuses.
    """
    dishes = _active_dishes(db_session, 2)
    order = _create_order(client, [dish.Id for dish in dishes]).json()["order"]
    order_id = order["id"]
    items = order["items"]

    assert _patch_status(client, order_id, "cooking").status_code == 200
    _patch_item_status(client, order_id, items[0]["id"], "completed")

    resp = _patch_status(client, order_id, "cancelled")
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["items"][0]["status"] == "completed"
    assert body["items"][1]["status"] == "pending"


def test_reprint_increments_print_count(client: TestClient, db_session) -> None:
    """补打接口：打印次数递增，返回柜台单与厨房单结果。

    Reprint endpoint: the print count increments and both targets are returned.
    """
    dish = _active_dishes(db_session, 1)[0]
    order_id = _create_order(client, [dish.Id]).json()["order"]["id"]

    resp = client.post(f"/api/orders/{order_id}/print", json={"target": "both"})
    assert resp.status_code == 200
    results = resp.json()
    assert [result["target"] for result in results] == ["counter", "kitchen"]
    assert all(result["ok"] for result in results)

    detail = client.get(f"/api/orders/{order_id}").json()
    assert detail["printCount"] == 1

    client.post(f"/api/orders/{order_id}/print", json={"target": "counter"})
    detail = client.get(f"/api/orders/{order_id}").json()
    assert detail["printCount"] == 2


def test_mock_print_writes_files(client: TestClient, db_session, data_dir: str) -> None:
    """mock 模式下下单会自动写入 printed 目录的小票文件。

    In mock mode, ordering writes ticket files into the printed directory.
    """
    dish = _active_dishes(db_session, 1)[0]
    resp = _create_order(client, [dish.Id])
    assert resp.status_code == 201

    printed_dir = Path(data_dir) / "printed"
    files = list(printed_dir.glob("*.txt"))
    assert files, "mock 打印未产生小票文件"
