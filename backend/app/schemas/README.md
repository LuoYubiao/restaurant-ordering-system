# schemas Pydantic 模型目录说明

存放接口的出入参模型（Pydantic v2），用于请求校验与响应序列化。

| 文件 | 说明 |
| --- | --- |
| `category.py` | 分类：`CategoryOut` / `CategoryCreate` / `CategoryUpdate` |
| `dish.py` | 菜品：`DishOut` / `DishCreate` / `DishUpdate` / `DishAvailabilityUpdate` |
| `order.py` | 订单：下单、明细、状态更新、打印请求与结果等模型 |
| `settings.py` | 设置：`PrinterSettings` / `SettingsOut` / `SettingsUpdate` / `SettingsStatus` |
| `common.py` | 通用模型（统一错误结构 `ErrorResponse`） |
| `__init__.py` | 统一导出 |

## 约定

- 所有 `*Out` 模型设置 `model_config = ConfigDict(from_attributes=True)`，便于直接从 ORM 对象转换。
- **金额字段统一以字符串形式对外暴露**，保留 2 位小数（如 `"12.00"`）。
- 时间字段以 ISO 字符串对外暴露（如 `"2026-11-03T12:30:00"`）。
