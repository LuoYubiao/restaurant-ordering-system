"""订单与订单明细 ORM 模型。

Order and order item ORM models.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Order(Base):
    """订单表。

    Order table.
    """

    __tablename__ = "Order"

    # 主键 ID / Primary key
    Id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 订单号（唯一）/ Order number (unique)
    OrderNo: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    # 桌号，打包订单可为空 / Table number, may be null for takeaway
    TableNo: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # 就餐方式：dine_in / takeaway / Dining type: dine_in / takeaway
    DiningType: Mapped[str] = mapped_column(String(16), nullable=False)
    # 订单状态 / Order status
    Status: Mapped[str] = mapped_column(String(16), nullable=False)
    # 订单总金额（分）/ Total amount in fen
    TotalAmount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 订单备注 / Order remark
    Remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 打印次数 / Print count
    PrintCount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 创建时间 / Created time
    CreatedTime: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # 更新时间 / Updated time
    UpdatedTime: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    # 订单明细（级联删除，按 Id 排序）/ Order items (cascade delete, ordered by Id)
    items: Mapped[List["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.Id",
    )


class OrderItem(Base):
    """订单明细表。

    Order item table.
    """

    __tablename__ = "OrderItem"

    # 主键 ID / Primary key
    Id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 所属订单 ID / Owning order id
    OrderId: Mapped[int] = mapped_column(
        Integer, ForeignKey("Order.Id"), nullable=False
    )
    # 菜品 ID / Dish id
    DishId: Mapped[int] = mapped_column(Integer, ForeignKey("Dish.Id"), nullable=False)
    # 下单时的菜品名称快照 / Dish name snapshot at order time
    DishName: Mapped[str] = mapped_column(String(128), nullable=False)
    # 下单时的单价（分）/ Unit price snapshot in fen
    Price: Mapped[int] = mapped_column(Integer, nullable=False)
    # 数量 / Quantity
    Quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # 口味/特殊要求备注 / Taste or special-request remark
    Remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 明细状态：pending / completed / Item status: pending / completed
    Status: Mapped[str] = mapped_column(String(16), nullable=False)
    # 出餐完成时间 / Completion time
    CompletedTime: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 所属订单 / Owning order
    order: Mapped["Order"] = relationship(back_populates="items")
