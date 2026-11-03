"""菜品相关的 Pydantic 模型。

Pydantic schemas for dishes.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DishOut(BaseModel):
    """菜品输出模型（金额为两位小数字符串）。

    Dish output schema (price as a string with two decimals).
    """

    model_config = ConfigDict(from_attributes=True)

    # 菜品 ID / Dish id
    id: int
    # 所属分类 ID / Owning category id
    categoryId: int
    # 菜品名称 / Dish name
    name: str
    # 价格（元，两位小数字符串）/ Price in yuan as a 2-decimal string
    price: str
    # 单位 / Unit
    unit: str = "份"
    # 描述 / Description
    description: Optional[str] = None
    # 图片地址 / Image URL
    imageUrl: Optional[str] = None
    # 是否有货 / Whether available
    isAvailable: bool = True
    # 是否启用 / Whether active
    isActive: bool = True
    # 排序序号 / Sort order
    sortOrder: int = 0


class DishCreate(BaseModel):
    """创建菜品的输入模型。

    Dish creation input schema.
    """

    # 所属分类 ID / Owning category id
    categoryId: int
    # 菜品名称 / Dish name
    name: str = Field(min_length=1, max_length=128)
    # 价格（元，两位小数字符串）/ Price in yuan as a 2-decimal string
    price: str
    # 单位 / Unit
    unit: str = "份"
    # 描述 / Description
    description: Optional[str] = None
    # 图片地址 / Image URL
    imageUrl: Optional[str] = None
    # 排序序号 / Sort order
    sortOrder: int = 0


class DishUpdate(BaseModel):
    """更新菜品的输入模型（全部字段可选）。

    Dish update input schema (all fields optional).
    """

    # 所属分类 ID / Owning category id
    categoryId: Optional[int] = None
    # 菜品名称 / Dish name
    name: Optional[str] = Field(default=None, max_length=128)
    # 价格（元，两位小数字符串）/ Price in yuan as a 2-decimal string
    price: Optional[str] = None
    # 单位 / Unit
    unit: Optional[str] = None
    # 描述 / Description
    description: Optional[str] = None
    # 图片地址 / Image URL
    imageUrl: Optional[str] = None
    # 是否有货 / Whether available
    isAvailable: Optional[bool] = None
    # 是否启用 / Whether active
    isActive: Optional[bool] = None
    # 排序序号 / Sort order
    sortOrder: Optional[int] = None


class DishAvailabilityUpdate(BaseModel):
    """更新菜品上下架（是否有货）的输入模型。

    Dish availability update input schema.
    """

    # 是否有货 / Whether available
    isAvailable: bool


class MenuCategoryOut(BaseModel):
    """菜单中的单个分类（含其菜品）。

    A single category in the menu, including its dishes.
    """

    # 分类 ID / Category id
    id: int
    # 分类名称 / Category name
    name: str
    # 排序序号 / Sort order
    sortOrder: int = 0
    # 该分类下的菜品 / Dishes under this category
    dishes: list[DishOut] = Field(default_factory=list)


class MenuOut(BaseModel):
    """点菜页整份菜单的输出模型。

    Whole-menu output schema for the ordering page.
    """

    # 店铺名称 / Shop name
    shopName: str
    # 分类列表（含菜品）/ Category list with dishes
    categories: list[MenuCategoryOut] = Field(default_factory=list)
