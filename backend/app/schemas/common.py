"""通用 Pydantic 模型。

Common Pydantic schemas.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """统一错误响应模型。

    Unified error response schema.
    """

    # 错误说明（中文可读信息）/ Error message (human readable)
    detail: str
    # 可选错误码 / Optional error code
    code: Optional[str] = None
