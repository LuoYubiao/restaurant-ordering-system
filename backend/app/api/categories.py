"""分类接口路由。

Category API router.

提供菜品分类的查询、创建、局部更新与软删除接口。
Provides endpoints to list, create, partially update and soft-delete dish
categories.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Category, Dish
from ..schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from .deps import get_db

logger = logging.getLogger(__name__)

# 分类接口路由 / Category router
router = APIRouter(tags=["categories"])

# 输入字段名到 ORM 属性的映射 / Input field names to ORM attribute mapping
_FIELD_TO_ATTR: dict[str, str] = {
    "name": "Name",
    "sortOrder": "SortOrder",
    "isActive": "IsActive",
}


def category_to_out(category: Category) -> CategoryOut:
    """把分类 ORM 对象转换为对外输出模型。

    Convert a category ORM object into the output schema.

    :param category: 分类 ORM 对象 / category ORM object
    :return: 分类输出模型 / category output schema
    """
    return CategoryOut(
        id=category.Id,
        name=category.Name,
        sortOrder=category.SortOrder,
        isActive=category.IsActive,
    )


def get_category_or_404(db: Session, category_id: int) -> Category:
    """获取分类（含已停用分类），不存在时抛出 404。

    Fetch a category, including inactive ones, raising 404 only when it is
    missing. Inactive is a state, not an absence, so it must stay editable.

    :param db: 数据库会话 / database session
    :param category_id: 分类 ID / category id
    :return: 分类 ORM 对象 / category ORM object
    """
    category = db.get(Category, category_id)
    if category is None:
        logger.info("Category not found, id=%s", category_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"分类不存在：{category_id}"
        )
    return category


def get_active_category_or_404(db: Session, category_id: int) -> Category:
    """获取未被软删除的分类，否则抛出 404。

    Fetch a non-soft-deleted category, raising 404 when it is missing or
    already inactive.

    :param db: 数据库会话 / database session
    :param category_id: 分类 ID / category id
    :return: 分类 ORM 对象 / category ORM object
    """
    category = db.get(Category, category_id)
    if category is None or not category.IsActive:
        logger.info("Category not found or inactive, id=%s", category_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"分类不存在：{category_id}"
        )
    return category


@router.get("/categories", response_model=List[CategoryOut])
def list_categories(
    includeInactive: bool = Query(
        False, description="是否包含已停用分类 / Whether to include inactive categories"
    ),
    db: Session = Depends(get_db),
) -> List[CategoryOut]:
    """查询分类列表，按排序号与 ID 升序返回。

    List categories ordered by sort order then id ascending.

    :param includeInactive: 是否包含已停用分类 / whether to include inactive categories
    :param db: 数据库会话 / database session
    :return: 分类输出列表 / list of category outputs
    """
    stmt = select(Category)
    if not includeInactive:
        stmt = stmt.where(Category.IsActive.is_(True))
    stmt = stmt.order_by(Category.SortOrder.asc(), Category.Id.asc())
    rows = db.scalars(stmt).all()
    logger.info("List categories, includeInactive=%s, count=%s", includeInactive, len(rows))
    return [category_to_out(row) for row in rows]


@router.post(
    "/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED
)
def create_category(
    payload: CategoryCreate, db: Session = Depends(get_db)
) -> CategoryOut:
    """创建分类。

    Create a new category.

    :param payload: 创建分类的输入 / category creation input
    :param db: 数据库会话 / database session
    :return: 创建后的分类输出 / created category output
    """
    category = Category(
        Name=payload.name,
        SortOrder=payload.sortOrder,
        IsActive=True,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    logger.info("Category created, id=%s, name=%s", category.Id, category.Name)
    return category_to_out(category)


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)
) -> CategoryOut:
    """局部更新分类（仅更新请求中提供的字段）。

    Partially update a category (only fields present in the request). Inactive
    categories stay editable so they can be re-enabled via ``isActive=true``.

    :param category_id: 分类 ID / category id
    :param payload: 更新分类的输入 / category update input
    :param db: 数据库会话 / database session
    :return: 更新后的分类输出 / updated category output
    """
    category = get_category_or_404(db, category_id)
    data = payload.model_dump(exclude_unset=True)
    for field, attr in _FIELD_TO_ATTR.items():
        if field in data and data[field] is not None:
            setattr(category, attr, data[field])
    db.commit()
    db.refresh(category)
    logger.info("Category updated, id=%s", category_id)
    return category_to_out(category)


@router.delete("/categories/{category_id}", response_model=CategoryOut)
def delete_category(
    category_id: int, db: Session = Depends(get_db)
) -> CategoryOut:
    """软删除分类（置 IsActive=False）。

    Soft-delete a category (set ``IsActive=False``). Refuses to delete when the
    category still holds any dish, including soft-deleted ones.

    :param category_id: 分类 ID / category id
    :param db: 数据库会话 / database session
    :return: 软删除后的分类输出 / soft-deleted category output
    """
    category = get_active_category_or_404(db, category_id)
    remaining = db.scalar(
        select(func.count()).select_from(Dish).where(Dish.CategoryId == category_id)
    )
    remaining = int(remaining or 0)
    if remaining:
        logger.info(
            "Category delete refused, id=%s still has %s dishes", category_id, remaining
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"该分类下还有 {remaining} 个菜品，请先移动或删除",
        )
    category.IsActive = False
    db.commit()
    db.refresh(category)
    logger.info("Category soft-deleted, id=%s", category_id)
    return category_to_out(category)
