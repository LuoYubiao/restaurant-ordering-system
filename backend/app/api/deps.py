"""API 依赖模块。

API dependencies module.
"""

from __future__ import annotations

from ..database import get_db

# 复用数据库会话依赖 / Re-export the database session dependency
__all__ = ["get_db"]
