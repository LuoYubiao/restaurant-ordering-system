"""初始种子数据模块。

Initial seed data module.

仅在数据库为空（``Category`` 表无记录）时写入默认分类与示例菜品，保证幂等。
Seeds default categories and sample dishes only when the database is empty
(the ``Category`` table has no rows), making it idempotent.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Category, Dish

logger = logging.getLogger(__name__)

# 默认分类与示例菜品（价格以「分」为单位）
# Default categories and sample dishes (prices in fen)
_DEFAULT_DATA: list[tuple[str, list[tuple[str, int, str]]]] = [
    (
        "热菜",
        [
            ("宫保鸡丁", 2800, "份"),
            ("麻婆豆腐", 1800, "份"),
            ("鱼香肉丝", 2600, "份"),
        ],
    ),
    (
        "凉菜",
        [
            ("拍黄瓜", 1200, "份"),
            ("口水鸡", 2200, "份"),
        ],
    ),
    (
        "主食",
        [
            ("米饭", 200, "碗"),
            ("蛋炒饭", 1500, "份"),
            ("手工面", 1600, "碗"),
        ],
    ),
    (
        "饮品",
        [
            ("可乐", 500, "听"),
            ("酸梅汤", 800, "杯"),
        ],
    ),
]


def seed_if_needed(db: Session) -> None:
    """按需写入初始种子数据（幂等）。

    Seed initial data on demand (idempotent). Does nothing when the
    ``Category`` table already contains rows.

    :param db: 数据库会话 / database session
    :return: None
    """
    existing = db.scalar(select(func.count()).select_from(Category))
    if existing:
        logger.info("Seed skipped, %s categories already exist", existing)
        return

    for category_index, (category_name, dishes) in enumerate(_DEFAULT_DATA):
        category = Category(
            Name=category_name,
            SortOrder=category_index,
            IsActive=True,
        )
        db.add(category)
        db.flush()
        for dish_index, (dish_name, price, unit) in enumerate(dishes):
            db.add(
                Dish(
                    CategoryId=category.Id,
                    Name=dish_name,
                    Price=price,
                    Unit=unit,
                    IsAvailable=True,
                    IsActive=True,
                    SortOrder=dish_index,
                )
            )

    db.commit()
    logger.info("Seed data inserted, %s categories created", len(_DEFAULT_DATA))
