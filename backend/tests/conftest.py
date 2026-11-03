"""测试公共夹具模块。

Shared pytest fixtures module.

每个测试使用独立的临时数据目录（通过 ``ROS_DATA_DIR`` 覆盖），并在使用前后
重置配置缓存与数据库引擎，保证测试之间互不干扰。
Each test uses an isolated temporary data directory (via ``ROS_DATA_DIR``) and
resets the config cache and database engine before/after use.
"""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient


def _reset_runtime() -> None:
    """重置配置缓存与数据库引擎。

    Reset the config cache and database engine.
    """
    from app import config, database

    config.reset_config_cache()
    database.reset_engine()


@pytest.fixture()
def data_dir(tmp_path, monkeypatch) -> Iterator[str]:
    """提供隔离的临时数据目录并设置环境变量。

    Provide an isolated temporary data directory and set the env var.

    :return: 临时目录路径字符串 / temp directory path as string
    """
    monkeypatch.setenv("ROS_DATA_DIR", str(tmp_path))
    _reset_runtime()
    yield str(tmp_path)
    _reset_runtime()


@pytest.fixture()
def client(data_dir) -> Iterator[TestClient]:
    """提供启动完成的 TestClient（使用全新数据库）。

    Provide a started TestClient backed by a fresh database.

    :return: 测试客户端 / test client
    """
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session(data_dir) -> Iterator["object"]:
    """提供已初始化数据库的会话。

    Provide a session bound to an initialized database.

    :return: 会话对象 / session object
    """
    from app import database

    database.init_db()
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()
