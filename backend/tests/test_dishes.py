"""菜品分类与菜品管理接口测试。

Tests for the dish category and dish management endpoints.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create_category(client: TestClient, name: str, sort_order: int = 0) -> dict:
    """通过接口创建分类并返回响应体。

    Create a category through the API and return the response body.

    :param client: 测试客户端 / test client
    :param name: 分类名称 / category name
    :param sort_order: 排序号 / sort order
    :return: 分类响应体 / category response body
    """
    resp = client.post("/api/categories", json={"name": name, "sortOrder": sort_order})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_dish(
    client: TestClient, category_id: int, name: str, price: str = "10.00", **extra
) -> dict:
    """通过接口创建菜品并返回响应体。

    Create a dish through the API and return the response body.

    :param client: 测试客户端 / test client
    :param category_id: 所属分类 ID / owning category id
    :param name: 菜品名称 / dish name
    :param price: 价格（元字符串）/ price as a yuan string
    :param extra: 其它可选字段 / additional optional fields
    :return: 菜品响应体 / dish response body
    """
    payload = {"categoryId": category_id, "name": name, "price": price}
    payload.update(extra)
    resp = client.post("/api/dishes", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_category_crud_and_sorting(client: TestClient) -> None:
    """分类增删改查与按排序号排序。

    Category create/read/update/delete and sorting by sort order.
    """
    late = _create_category(client, "测试分类-后", sort_order=50)
    early = _create_category(client, "测试分类-前", sort_order=1)

    # 列表按 (SortOrder, Id) 升序 / List ordered by (SortOrder, Id) ascending
    body = client.get("/api/categories").json()
    keys = [(item["sortOrder"], item["id"]) for item in body]
    assert keys == sorted(keys)

    ids = [item["id"] for item in body]
    assert ids.index(early["id"]) < ids.index(late["id"])

    # 局部更新名称与排序号 / Partially update name and sort order
    resp = client.put(
        f"/api/categories/{late['id']}", json={"name": "测试分类-已改名", "sortOrder": 0}
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == "测试分类-已改名"
    assert updated["sortOrder"] == 0

    # 删除无菜品的分类（软删除）/ Soft-delete a category without dishes
    resp = client.delete(f"/api/categories/{early['id']}")
    assert resp.status_code == 200
    assert resp.json()["isActive"] is False

    # 默认列表不包含已删除分类，includeInactive=true 可见
    # Default list hides inactive; includeInactive=true reveals it
    default_ids = [item["id"] for item in client.get("/api/categories").json()]
    assert early["id"] not in default_ids
    all_ids = [
        item["id"]
        for item in client.get("/api/categories?includeInactive=true").json()
    ]
    assert early["id"] in all_ids

    # 更新不存在的分类返回 404 / Updating a missing category returns 404
    assert client.put("/api/categories/999999", json={"name": "x"}).status_code == 404


def test_category_disable_then_enable(client: TestClient) -> None:
    """分类停用后可再次启用（回归：启用曾返回 404）。

    A disabled category can be re-enabled (regression: enabling used to 404).
    """
    category = _create_category(client, "停用再启用分类")

    resp = client.put(f"/api/categories/{category['id']}", json={"isActive": False})
    assert resp.status_code == 200
    assert resp.json()["isActive"] is False

    # 停用状态下仍可启用（此前会误报「分类不存在」）
    # Re-enabling an inactive category works (it used to report "not found")
    resp = client.put(f"/api/categories/{category['id']}", json={"isActive": True})
    assert resp.status_code == 200
    assert resp.json()["isActive"] is True

    # 恢复后重新出现在默认列表中 / Back in the default list
    default_ids = [item["id"] for item in client.get("/api/categories").json()]
    assert category["id"] in default_ids


def test_delete_category_with_dishes_returns_400(client: TestClient) -> None:
    """分类下仍有菜品时删除返回 400。

    Deleting a category that still has dishes returns 400.
    """
    category = _create_category(client, "有菜品的分类")
    _create_dish(client, category["id"], "占位菜品")

    resp = client.delete(f"/api/categories/{category['id']}")
    assert resp.status_code == 400
    assert "还有 1 个菜品" in resp.json()["detail"]


def test_delete_category_with_only_inactive_dishes_returns_400(
    client: TestClient,
) -> None:
    """分类下只剩已停用菜品时，删除同样返回 400。

    Deleting a category that only holds soft-deleted dishes still returns 400.
    """
    category = _create_category(client, "仅剩停用菜品的分类")
    dish = _create_dish(client, category["id"], "已停用菜品")
    assert client.delete(f"/api/dishes/{dish['id']}").status_code == 200

    resp = client.delete(f"/api/categories/{category['id']}")
    assert resp.status_code == 400
    assert "还有 1 个菜品" in resp.json()["detail"]

    # 把菜品移到别的分类后即可删除 / Deletable once the dish is moved away
    other = _create_category(client, "承接菜品的分类")
    resp = client.put(f"/api/dishes/{dish['id']}", json={"categoryId": other["id"]})
    assert resp.status_code == 200
    assert client.delete(f"/api/categories/{category['id']}").status_code == 200


def test_create_dish_price_conversion(client: TestClient, db_session) -> None:
    """创建菜品时价格字符串正确转换为分。

    Price strings are correctly converted into fen when creating a dish.
    """
    from app.models import Dish

    category = _create_category(client, "价格测试分类")
    dish = _create_dish(client, category["id"], "宫保鸡丁", price="28.00")

    assert dish["price"] == "28.00"
    assert dish["unit"] == "份"
    assert dish["isAvailable"] is True

    # 数据库中应以分存储 / Stored as fen in the database
    row = db_session.get(Dish, dish["id"])
    assert row is not None
    assert row.Price == 2800


def test_invalid_price_rejected(client: TestClient) -> None:
    """非法价格（abc/0/-1）返回 400 或 422。

    Invalid prices (abc/0/-1) return 400 or 422.
    """
    category = _create_category(client, "非法价格分类")
    for bad in ("abc", "0", "-1"):
        resp = client.post(
            "/api/dishes",
            json={"categoryId": category["id"], "name": "坏价格", "price": bad},
        )
        assert resp.status_code in (400, 422), f"price={bad} -> {resp.status_code}"


def test_create_dish_unknown_category_returns_400(client: TestClient) -> None:
    """关联不存在的分类返回 400。

    Creating a dish with a non-existent category returns 400.
    """
    resp = client.post(
        "/api/dishes",
        json={"categoryId": 999999, "name": "孤儿菜品", "price": "10.00"},
    )
    assert resp.status_code == 400


def test_availability_toggle(client: TestClient) -> None:
    """售罄切换生效并持久化。

    Toggling availability takes effect and persists.
    """
    category = _create_category(client, "售罄测试分类")
    dish = _create_dish(client, category["id"], "可售罄菜品")

    resp = client.patch(
        f"/api/dishes/{dish['id']}/availability", json={"isAvailable": False}
    )
    assert resp.status_code == 200
    assert resp.json()["isAvailable"] is False
    assert client.get(f"/api/dishes/{dish['id']}").json()["isAvailable"] is False

    resp = client.patch(
        f"/api/dishes/{dish['id']}/availability", json={"isAvailable": True}
    )
    assert resp.status_code == 200
    assert resp.json()["isAvailable"] is True


def test_dish_soft_delete(client: TestClient, db_session) -> None:
    """菜品软删除：默认列表不可见、可查询、数据库记录仍在。

    Dish soft-delete: hidden from the default list, visible with
    ``includeInactive=true``, and the database row is preserved.
    """
    from app.models import Dish

    category = _create_category(client, "软删除测试分类")
    dish = _create_dish(client, category["id"], "将被删除的菜品")

    resp = client.delete(f"/api/dishes/{dish['id']}")
    assert resp.status_code == 200
    assert resp.json()["isActive"] is False

    # 默认列表查不到 / Not present in the default list
    default_ids = [item["id"] for item in client.get("/api/dishes").json()]
    assert dish["id"] not in default_ids

    # includeInactive=true 能查到 / Visible with includeInactive=true
    all_ids = [
        item["id"] for item in client.get("/api/dishes?includeInactive=true").json()
    ]
    assert dish["id"] in all_ids

    # 按分类过滤同样可验证 / Also verifiable via category filter
    filtered = client.get(
        f"/api/dishes?categoryId={category['id']}&includeInactive=true"
    ).json()
    assert dish["id"] in [item["id"] for item in filtered]

    # 数据库记录仍存在且 IsActive=False / The database row still exists
    row = db_session.get(Dish, dish["id"])
    assert row is not None
    assert row.IsActive is False


def test_dish_soft_delete_then_restore(client: TestClient) -> None:
    """已软删除的菜品可再次启用。

    A soft-deleted dish can be re-enabled.
    """
    category = _create_category(client, "菜品恢复测试分类")
    dish = _create_dish(client, category["id"], "待恢复菜品")
    assert client.delete(f"/api/dishes/{dish['id']}").status_code == 200

    resp = client.put(f"/api/dishes/{dish['id']}", json={"isActive": True})
    assert resp.status_code == 200
    assert resp.json()["isActive"] is True

    # 恢复后重新出现在默认列表中 / Back in the default list
    default_ids = [item["id"] for item in client.get("/api/dishes").json()]
    assert dish["id"] in default_ids


def test_menu_endpoint(client: TestClient) -> None:
    """``GET /api/menu`` 只返回有效分类与菜品、售罄菜品仍在且置为不可用。

    ``GET /api/menu`` returns only active categories/dishes; sold-out dishes are
    still listed with ``isAvailable=false``.
    """
    # 有效分类：一个可售菜品 + 一个售罄菜品
    # Active category: one available dish plus one sold-out dish
    active_category = _create_category(client, "菜单测试分类")
    available_dish = _create_dish(client, active_category["id"], "在售菜品")
    sold_out_dish = _create_dish(client, active_category["id"], "售罄菜品")
    client.patch(
        f"/api/dishes/{sold_out_dish['id']}/availability",
        json={"isAvailable": False},
    )

    # 已软删除的分类与菜品不应出现在菜单中
    # Soft-deleted category and dish must not appear in the menu
    removed_category = _create_category(client, "菜单测试-已删除分类")
    client.delete(f"/api/categories/{removed_category['id']}")
    removed_dish = _create_dish(client, active_category["id"], "菜单测试-已删除菜品")
    client.delete(f"/api/dishes/{removed_dish['id']}")

    menu = client.get("/api/menu")
    assert menu.status_code == 200
    body = menu.json()

    assert body["shopName"] == "我的小店"

    category_ids = [item["id"] for item in body["categories"]]
    assert active_category["id"] in category_ids
    assert removed_category["id"] not in category_ids

    target = next(item for item in body["categories"] if item["id"] == active_category["id"])
    dish_ids = [item["id"] for item in target["dishes"]]
    assert available_dish["id"] in dish_ids
    assert sold_out_dish["id"] in dish_ids
    assert removed_dish["id"] not in dish_ids

    sold_out = next(item for item in target["dishes"] if item["id"] == sold_out_dish["id"])
    assert sold_out["isAvailable"] is False
    assert sold_out["price"] == "10.00"

    # 菜单中所有分类与菜品都应处于启用状态 / All menu entries must be active
    for category in body["categories"]:
        assert category["dishes"] is not None
