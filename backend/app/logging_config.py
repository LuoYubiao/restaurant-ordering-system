"""日志配置模块。

Logging configuration module.

日志同时输出到文件（按天滚动）与控制台，日志正文统一使用英文。
Logs are written both to a daily-rotating file and to the console; all log
messages are in English.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler

from .paths import get_logs_dir

# 日志格式：时间 | 级别 | 记录器 | 消息 / Log format
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
# 日志文件保留天数 / Number of days to keep rotated log files
LOG_BACKUP_DAYS = 14
# 标记是否已初始化，避免重复添加 handler / Guard flag to stay idempotent
_initialized = False


def setup_logging() -> None:
    """初始化日志系统（幂等）。

    Initialize the logging system (idempotent). Adds a daily-rotating file
    handler and a console handler to the root logger.

    :return: None
    """
    global _initialized
    root = logging.getLogger()
    if _initialized and any(
        isinstance(h, TimedRotatingFileHandler) for h in root.handlers
    ):
        return

    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "app.log"

    formatter = logging.Formatter(LOG_FORMAT)

    # 每天 00:00 滚动，保留 14 天 / Rotate at midnight, keep 14 days
    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        interval=1,
        backupCount=LOG_BACKUP_DAYS,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    _initialized = True
    logging.getLogger(__name__).info("Logging initialized, file=%s", log_file)
