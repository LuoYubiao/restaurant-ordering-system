"""菜品接口路由。

Dish API router.

提供菜品的查询、创建、更新、软删除、售罄切换，以及供点菜页使用的整份菜单
接口。
Provides endpoints to list, create, update, soft-delete and toggle availability
of dishes, plus a whole-menu endpoint for the ordering page.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_config
from ..models import Category, Dish
from ..money import fen_to_yuan, yuan_to_fen
from ..schemas.dish import (
    DishAvailabilityUpdate,
    DishCreate,
    DishOut,
    DishUpdate,
    MenuCategoryOut,
    MenuOut,
)
from .deps import get_db

logger = logging.getLogger(__name__)

# 菜品接口路由 / Dish router
router = APIRouter(tags=["dishes"])

# 可直接映射到 ORM 属性的输入字段 / Input fields that map directly to ORM attributes
_DIRECT_FIELD_TO_ATTR: dict[str, str] = {
    "categoryId": "CategoryId",
    "name": "Name",
    "unit": "Unit",
    "description": "Description",
    "imageUrl": "ImageUrl",
    "isAvailable": "IsAvailable",
    "isActive": "IsActive",
    "sortOrder": "SortOrder",
}

# 允许显式置空（null）的可选文本字段 / Optional text fields that may be explicitly cleared
_NULLABLE_FIELDS = frozenset({"description", "imageUrl"})


def dish_to_out(dish: Dish) -> DishOut:
    """把菜品 ORM 对象转换为对外输出模型（金额转为两位小数字符串）。

    Convert a dish ORM object into the output schema, formatting the price as a
    two-decimal yuan string.

    :param dish: 菜品 ORM 对象 / dish ORM object
    :return: 菜品输出模型 / dish output schema
    """
    return DishOut(
        id=dish.Id,
        categoryId=dish.CategoryId,
        name=dish.Name,
        price=fen_to_yuan(dish.Price),
        unit=dish.Unit,
        description=dish.Description,
        imageUrl=dish.ImageUrl,
        isAvailable=dish.IsAvailable,
        isActive=dish.IsActive,
        sortOrder=dish.SortOrder,
    )


def _parse_price(price: str) -> int:
    """把元字符串解析为以分为单位的整数，非法或非正数时返回 400。

    Parse a yuan string into an integer amount in fen, raising 400 when the
    value is invalid or not positive.

    :param price: 价格（元字符串）/ price as a yuan string
    :return: 以分为单位的整数价格 / price in fen as an integer
    """
    try:
        fen = yuan_to_fen(price)
    except ValueError as exc:
        logger.info("Invalid price rejected: %r", price)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"价格非法：{price!r}"
        ) from exc
    if fen <= 0:
        logger.info("Non-positive price rejected: %r", price)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="价格必须大于 0"
        )
    return fen


def _get_usable_category(db: Session, category_id: int) -> Category:
    """校验分类存在且未软删除，否则返回 400。

    Ensure the category exists and is not soft-deleted, raising 400 otherwise.

    :param db: 数据库会话 / database session
    :param category_id: 分类 ID / category id
    :return: 分类 ORM 对象 / category ORM object
    """
    category = db.get(Category, category_id)
    if category is None or not category.IsActive:
        logger.info("Dish rejected, category missing or inactive: %s", category_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"分类不存在或已停用：{category_id}",
        )
    return category


def _get_dish_or_404(db: Session, dish_id: int) -> Dish:
    """获取菜品，不存在时返回 404。

    Fetch a dish by id, raising 404 when it does not exist.

    :param db: 数据库会话 / database session
    :param dish_id: 菜品 ID / dish id
    :return: 菜品 ORM 对象 / dish ORM object
    """
    dish = db.get(Dish, dish_id)
    if dish is None:
        logger.info("Dish not found, id=%s", dish_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"菜品不存在：{dish_id}"
        )
    return dish


@router.get("/dishes", response_model=List[DishOut])
def list_dishes(
    categoryId: Optional[int] = Query(
        None, description="按分类过滤 / Filter by category id"
    ),
    includeInactive: bool = Query(
        False, description="是否包含已删除菜品 / Whether to include soft-deleted dishes"
    ),
    db: Session = Depends(get_db),
) -> List[DishOut]:
    """查询菜品列表，按排序号与 ID 升序返回，可按分类过滤。

    List dishes ordered by sort order then id ascending, optionally filtered by
    category.

    :param categoryId: 分类 ID 过滤 / category id filter
    :param includeInactive: 是否包含已软删除菜品 / whether to include soft-deleted dishes
    :param db: 数据库会话 / database session
    :return: 菜品输出列表 / list of dish outputs
    """
    stmt = select(Dish)
    if not includeInactive:
        stmt = stmt.where(Dish.IsActive.is_(True))
    if categoryId is not None:
        stmt = stmt.where(Dish.CategoryId == categoryId)
    stmt = stmt.order_by(Dish.SortOrder.asc(), Dish.Id.asc())
    rows = db.scalars(stmt).all()
    logger.info(
        "List dishes, categoryId=%s, includeInactive=%s, count=%s",
        categoryId,
        includeInactive,
        len(rows),
    )
    return [dish_to_out(row) for row in rows]


@router.get("/menu", response_model=MenuOut)
def get_menu(db: Session = Depends(get_db)) -> MenuOut:
    """获取整份菜单（仅未软删除的分类与菜品，售罄菜品仍返回）。

    Return the whole menu with only non-deleted categories and dishes.
    Sold-out dishes are still returned with ``isAvailable=false`` so the client
    can grey them out.

    :param db: 数据库会话 / database session
    :return: 菜单输出模型 / menu output schema
    """
    categories = db.scalars(
        select(Category)
        .where(Category.IsActive.is_(True))
        .order_by(Category.SortOrder.asc(), Category.Id.asc())
    ).all()
    dishes = db.scalars(
        select(Dish)
        .where(Dish.IsActive.is_(True))
        .order_by(Dish.SortOrder.asc(), Dish.Id.asc())
    ).all()

    grouped: Dict[int, List[DishOut]] = {}
    for dish in dishes:
        grouped.setdefault(dish.CategoryId, []).append(dish_to_out(dish))

    menu_categories = [
        MenuCategoryOut(
            id=category.Id,
            name=category.Name,
            sortOrder=category.SortOrder,
            dishes=grouped.get(category.Id, []),
        )
        for category in categories
    ]
    logger.info("Menu built, categories=%s, dishes=%s", len(menu_categories), len(dishes))
    return MenuOut(shopName=get_config().shopName, categories=menu_categories)


@router.get("/dishes/{dish_id}", response_model=DishOut)
def get_dish(dish_id: int, db: Session = Depends(get_db)) -> DishOut:
    """查询单个菜品详情。

    Fetch a single dish by id.

    :param dish_id: 菜品 ID / dish id
    :param db: 数据库会话 / database session
    :return: 菜品输出 / dish output
    """
    dish = _get_dish_or_404(db, dish_id)
    return dish_to_out(dish)


@router.post("/dishes", response_model=DishOut, status_code=status.HTTP_201_CREATED)
def create_dish(payload: DishCreate, db: Session = Depends(get_db)) -> DishOut:
    """创建菜品（校验分类有效且价格合法）。

    Create a dish, validating that the category is usable and the price is a
    valid positive amount.

    :param payload: 创建菜品的输入 / dish creation input
    :param db: 数据库会话 / database session
    :return: 创建后的菜品输出 / created dish output
    """
    _get_usable_category(db, payload.categoryId)
    fen = _parse_price(payload.price)
    dish = Dish(
        CategoryId=payload.categoryId,
        Name=payload.name,
        Price=fen,
        Unit=payload.unit,
        Description=payload.description,
        ImageUrl=payload.imageUrl,
        SortOrder=payload.sortOrder,
        IsAvailable=True,
        IsActive=True,
    )
    db.add(dish)
    db.commit()
    db.refresh(dish)
    logger.info("Dish created, id=%s, priceFen=%s", dish.Id, fen)
    return dish_to_out(dish)


@router.put("/dishes/{dish_id}", response_model=DishOut)
def update_dish(
    dish_id: int, payload: DishUpdate, db: Session = Depends(get_db)
) -> DishOut:
    """局部更新菜品（仅更新请求中提供的字段）。

    Partially update a dish (only fields present in the request). ``description``
    and ``imageUrl`` may be explicitly cleared with ``null``.

    :param dish_id: 菜品 ID / dish id
    :param payload: 更新菜品的输入 / dish update input
    :param db: 数据库会话 / database session
    :return: 更新后的菜品输出 / updated dish output
    """
    dish = _get_dish_or_404(db, dish_id)
    data = payload.model_dump(exclude_unset=True)

    # 价格需单独解析为分 / Price is parsed into fen separately
    if "price" in data and data["price"] is not None:
        dish.Price = _parse_price(data["price"])

    for field, attr in _DIRECT_FIELD_TO_ATTR.items():
        if field not in data:
            continue
        value = data[field]
        # 非空字段若传 null 则忽略；可空文本字段允许显式清空
        # Ignore null for non-nullable fields; nullable text fields may be cleared.
        if value is None and field not in _NULLABLE_FIELDS:
            continue
        if field == "categoryId" and value is not None:
            _get_usable_category(db, value)
        setattr(dish, attr, value)

    db.commit()
    db.refresh(dish)
    logger.info("Dish updated, id=%s", dish_id)
    return dish_to_out(dish)


@router.delete("/dishes/{dish_id}", response_model=DishOut)
def delete_dish(dish_id: int, db: Session = Depends(get_db)) -> DishOut:
    """软删除菜品（置 IsActive=False，保留历史订单引用）。

    Soft-delete a dish (set ``IsActive=False``) to preserve references from
    historical orders.

    :param dish_id: 菜品 ID / dish id
    :param db: 数据库会话 / database session
    :return: 软删除后的菜品输出 / soft-deleted dish output
    """
    dish = _get_dish_or_404(db, dish_id)
    dish.IsActive = False
    db.commit()
    db.refresh(dish)
    logger.info("Dish soft-deleted, id=%s", dish_id)
    return dish_to_out(dish)


@router.patch("/dishes/{dish_id}/availability", response_model=DishOut)
def update_dish_availability(
    dish_id: int, payload: DishAvailabilityUpdate, db: Session = Depends(get_db)
) -> DishOut:
    """切换菜品售罄状态。

    Toggle a dish's sold-out (availability) state.

    :param dish_id: 菜品 ID / dish id
    :param payload: 更新可用性的输入 / availability update input
    :param db: 数据库会话 / database session
    :return: 更新后的菜品输出 / updated dish output
    """
    dish = _get_dish_or_404(db, dish_id)
    dish.IsAvailable = payload.isAvailable
    db.commit()
    db.refresh(dish)
    logger.info("Dish availability updated, id=%s, isAvailable=%s", dish_id, dish.IsAvailable)
    return dish_to_out(dish)
