# models ORM 模型目录说明

存放数据库表结构定义（SQLAlchemy 2.x 声明式模型）与相关枚举。

| 文件 | 说明 |
| --- | --- |
| `enums.py` | 枚举（订单状态、明细状态、就餐方式）及中文文案映射 |
| `category.py` | `Category` 菜品分类表 |
| `dish.py` | `Dish` 菜品表 |
| `order.py` | `Order` 订单表与 `OrderItem` 订单明细表 |
| `__init__.py` | 统一导出全部模型与枚举 |

## 命名约定

- 数据库列名使用**驼峰命名**，如 `CreatedTime`、`IsActive`、`CategoryId`。
- 时间字段属性名以 `Time` 结尾。
- 布尔字段使用 `Is` 前缀。
- 金额字段（如 `Price`、`TotalAmount`）为以「分」为单位的整数。
