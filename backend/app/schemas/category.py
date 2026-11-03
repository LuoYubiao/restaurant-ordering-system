"""分类相关的 Pydantic 模型。

Pydantic schemas for categories.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CategoryOut(BaseModel):
    """分类输出模型。

    Category output schema.
    """

    model_config = ConfigDict(from_attributes=True)

    # 分类 ID / Category id
    id: int
    # 分类名称 / Category name
    name: str
    # 排序序号 / Sort order
    sortOrder: int = 0
    # 是否启用 / Whether active
    isActive: bool = True


class CategoryCreate(BaseModel):
    """创建分类的输入模型。

    Category creation input schema.
    """

    # 分类名称 / Category name
    name: str = Field(min_length=1, max_length=64)
    # 排序序号 / Sort order
    sortOrder: int = 0


class CategoryUpdate(BaseModel):
    """更新分类的输入模型（全部字段可选）。

    Category update input schema (all fields optional).
    """

    # 分类名称 / Category name
    name: Optional[str] = Field(default=None, max_length=64)
    # 排序序号 / Sort order
    sortOrder: Optional[int] = None
    # 是否启用 / Whether active
    isActive: Optional[bool] = None
