"""营业统计接口路由。

Revenue statistics API router.

提供只读的营业额统计查询接口。
Provides a read-only endpoint for revenue statistics.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..schemas.stats import RevenueStatsOut
from ..services import stats_service
from .deps import get_db

logger = logging.getLogger(__name__)

# 营业统计接口路由 / Revenue statistics router
router = APIRouter(tags=["stats"])


@router.get("/stats/revenue", response_model=RevenueStatsOut)
def get_revenue_stats(
    range_name: str = Query(default=stats_service.RANGE_TODAY, alias="range"),
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """查询指定区间的营业额统计。

    Query revenue statistics for the requested range.

    :param range_name: 区间标识（today / 7d / 30d / custom）/ range identifier
    :param start: 自定义起始日期（YYYY-MM-DD）/ custom start date
    :param end: 自定义结束日期（YYYY-MM-DD）/ custom end date
    :param db: 数据库会话 / database session
    :return: 统计结果 / statistics result
    """
    try:
        return stats_service.get_revenue_stats(db, range_name, start, end)
    except ValueError as exc:
        logger.info("Invalid revenue stats range rejected: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
