"""数据库访问模块（SQLAlchemy 2.x）。

Database access module (SQLAlchemy 2.x).

使用本地 SQLite 文件（``data/restaurant.db``）作为存储，开启 WAL 日志模式
与外键约束。引擎采用懒加载单例，便于测试中重置。
Uses a local SQLite file (``data/restaurant.db``) with WAL journal mode and
foreign keys enabled. The engine is a lazily-created singleton so tests can
reset it easily.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .paths import get_data_dir

logger = logging.getLogger(__name__)

# 所有 ORM 模型的声明基类 / Declarative base for all ORM models
Base = declarative_base()

# 懒加载的引擎单例 / Lazily-created engine singleton
_engine: Optional[Engine] = None


class SessionLocal(sessionmaker):
    """会话工厂，调用时自动确保引擎已初始化。

    Session factory that ensures the engine is initialized when called. This
    allows downstream code to simply do ``SessionLocal()`` without worrying
    about engine bootstrap order.
    """

    def __call__(self, **local_kw):  # type: ignore[override]
        """创建会话，创建前确保引擎就绪。

        Create a session, ensuring the engine is ready beforehand.
        """
        get_engine()
        return super().__call__(**local_kw)


# 全局会话工厂实例 / Global session factory instance
SessionLocal = SessionLocal(autoflush=False, autocommit=False, future=True)


def _configure_sqlite(engine: Engine) -> None:
    """为 SQLite 连接注册 PRAGMA 设置。

    Register PRAGMA settings for SQLite connections.

    :param engine: 目标引擎 / target engine
    """

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        """连接建立时执行 PRAGMA（WAL 与外键）。

        Execute PRAGMAs (WAL and foreign keys) on each new connection.
        """
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def get_engine() -> Engine:
    """获取引擎单例（首次调用时创建）。

    Return the engine singleton, creating it on first use.

    :return: SQLAlchemy 引擎 / SQLAlchemy engine
    """
    global _engine
    if _engine is None:
        db_path = get_data_dir() / "restaurant.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            future=True,
        )
        _configure_sqlite(_engine)
        SessionLocal.configure(bind=_engine)
        logger.info("Database engine created, path=%s", db_path)
    return _engine


def reset_engine() -> None:
    """重置引擎与会话工厂（测试用）。

    Reset the engine and session factory (for tests).
    """
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
    logger.info("Database engine reset")


def init_db() -> None:
    """创建所有数据表（幂等）。

    Create all database tables (idempotent).
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured")


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：提供数据库会话并在请求结束后关闭。

    FastAPI dependency: yield a database session and always close it.

    :return: 会话生成器 / session generator
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """上下文管理器：自动提交/回滚并关闭会话。

    Context manager: automatically commit/rollback and close the session.

    :return: 会话上下文 / session context
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
