"""API 路由包，聚合所有子路由。

API routers package aggregating all sub-routers.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import categories, dishes, orders, settings, stats, stream

# 统一 API 前缀路由 / Unified API router with the ``/api`` prefix
api_router = APIRouter(prefix="/api")
api_router.include_router(categories.router)
api_router.include_router(dishes.router)
api_router.include_router(orders.router)
api_router.include_router(stream.router)
api_router.include_router(settings.router)
api_router.include_router(stats.router)

# 对外导出清单 / Public export list
__all__ = ["api_router"]
