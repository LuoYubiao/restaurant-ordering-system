"""菜品 ORM 模型。

Dish ORM model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Dish(Base):
    """菜品表。

    Dish table.
    """

    __tablename__ = "Dish"

    # 主键 ID / Primary key
    Id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 所属分类 ID / Owning category id
    CategoryId: Mapped[int] = mapped_column(
        Integer, ForeignKey("Category.Id"), nullable=False
    )
    # 菜品名称 / Dish name
    Name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 价格（以「分」为单位的整数）/ Price in fen (integer)
    Price: Mapped[int] = mapped_column(Integer, nullable=False)
    # 单位（如 份 / 杯）/ Unit (e.g. 份 / 杯)
    Unit: Mapped[str] = mapped_column(String(16), default="份", nullable=False)
    # 菜品描述 / Dish description
    Description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 图片地址 / Image URL
    ImageUrl: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # 是否有货（未售罄）/ Whether available (not sold out)
    IsAvailable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 排序序号 / Sort order
    SortOrder: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 是否启用（软删除标记）/ Whether active (soft-delete flag)
    IsActive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 创建时间 / Created time
    CreatedTime: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # 更新时间 / Updated time
    UpdatedTime: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    # 所属分类 / Owning category
    category: Mapped["Category"] = relationship(back_populates="dishes")
