"""FastAPI 应用装配模块。

FastAPI application assembly module.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles

from .api import api_router
from .config import get_config
from .database import init_db, session_scope
from .logging_config import setup_logging
from .paths import ensure_runtime_dirs, get_frontend_dir
from .seed import seed_if_needed
from .version import __version__

logger = logging.getLogger(__name__)

# 页面尚未生成时的占位 HTML 模板
# Placeholder HTML template used when a page file does not exist yet
_PLACEHOLDER_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>页面尚未生成</title>
</head>
<body style="font-family: system-ui, sans-serif; padding: 40px; color: #333;">
  <h2>页面尚未生成</h2>
  <p>目标文件：{path}</p>
</body>
</html>
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时准备目录、日志、数据库与种子数据。

    Application lifespan: prepare directories, logging, database and seed data
    on startup.

    :param app: FastAPI 应用实例 / FastAPI application instance
    """
    ensure_runtime_dirs()
    setup_logging()
    # 加载配置（不存在时写入默认 config.json）/ Load config, writing defaults when missing
    get_config()
    init_db()
    with session_scope() as db:
        seed_if_needed(db)
    logger.info("Application startup complete, version=%s", __version__)
    yield
    logger.info("Application shutdown")


def _page_response(relative_path: str) -> Response:
    """返回页面文件；文件不存在时返回占位 HTML。

    Return a page file response; fall back to a placeholder HTML when the file
    does not exist.

    :param relative_path: 相对前端目录的页面路径 / page path relative to the frontend dir
    :return: 页面响应 / page response
    """
    file_path: Path = get_frontend_dir() / relative_path
    if file_path.exists():
        return FileResponse(file_path)
    logger.warning("Page file missing, serving placeholder: %s", file_path)
    return HTMLResponse(_PLACEHOLDER_TEMPLATE.format(path=relative_path))


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。

    Create and configure the FastAPI application.

    :return: FastAPI 应用实例 / FastAPI application instance
    """
    app = FastAPI(title="餐饮小店点菜系统", version=__version__, lifespan=lifespan)

    # 静态资源挂载 / Mount static assets
    static_dir = get_frontend_dir() / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> Response:
        """首页重定向到柜台点菜页。

        Redirect the root path to the counter page.
        """
        return RedirectResponse(url="/counter", status_code=302)

    @app.get("/counter", include_in_schema=False)
    def counter_page() -> Response:
        """柜台点菜页。

        Counter ordering page.
        """
        return _page_response("counter/index.html")

    @app.get("/kitchen", include_in_schema=False)
    def kitchen_page() -> Response:
        """厨房看板页。

        Kitchen display page.
        """
        return _page_response("kitchen/index.html")

    @app.get("/admin", include_in_schema=False)
    def admin_page() -> Response:
        """菜品管理页。

        Dish management page.
        """
        return _page_response("admin/index.html")

    @app.get("/settings", include_in_schema=False)
    def settings_page() -> Response:
        """系统设置页。

        System settings page.
        """
        return _page_response("settings/index.html")

    @app.get("/stats", include_in_schema=False)
    def stats_page() -> Response:
        """营业统计页。

        Revenue statistics page.
        """
        return _page_response("stats/index.html")

    @app.get("/health")
    def health() -> dict:
        """健康检查接口。

        Health check endpoint.

        :return: 状态、版本与当前时间 / status, version and current time
        """
        return {
            "status": "ok",
            "version": __version__,
            "time": datetime.now().isoformat(),
        }

    app.include_router(api_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """全局未捕获异常处理，返回统一 ``detail`` 结构。

        Global handler for unhandled exceptions, returning a unified
        ``detail`` structure.

        :param request: 请求对象 / request object
        :param exc: 异常对象 / exception object
        :return: 统一错误响应 / unified error response
        """
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return app


# 模块级应用实例，供 ``uvicorn app.main:app`` 使用
# Module-level app instance for ``uvicorn app.main:app``
app = create_app()
