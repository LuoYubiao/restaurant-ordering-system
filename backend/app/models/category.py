"""分类 ORM 模型。

Category ORM model.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Category(Base):
    """菜品分类表。

    Dish category table.
    """

    __tablename__ = "Category"

    # 主键 ID / Primary key
    Id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 分类名称 / Category name
    Name: Mapped[str] = mapped_column(String(64), nullable=False)
    # 排序序号，越小越靠前 / Sort order, smaller first
    SortOrder: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 是否启用（软删除标记）/ Whether active (soft-delete flag)
    IsActive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 创建时间 / Created time
    CreatedTime: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # 更新时间 / Updated time
    UpdatedTime: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    # 该分类下的菜品 / Dishes belonging to this category
    dishes: Mapped[List["Dish"]] = relationship(back_populates="category")
