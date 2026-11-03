# api 接口路由目录说明

存放 HTTP 接口路由（FastAPI `APIRouter`）。

| 文件 | 说明 |
| --- | --- |
| `__init__.py` | 聚合子路由，统一挂载到 `/api` 前缀 |
| `deps.py` | 公共依赖（当前导出数据库会话依赖 `get_db`） |
| `categories.py` | 分类相关接口（`tags=["categories"]`） |
| `dishes.py` | 菜品相关接口（`tags=["dishes"]`） |
| `orders.py` | 订单相关接口（`tags=["orders"]`） |
| `stream.py` | 实时事件流（SSE）（`tags=["stream"]`） |
| `settings.py` | 系统设置接口（`tags=["settings"]`） |

> 说明：当前各子模块仅创建了空的 `router` 骨架，具体 endpoint 由后续任务实现。
