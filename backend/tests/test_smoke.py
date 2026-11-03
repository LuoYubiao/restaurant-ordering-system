"""冒烟测试：验证应用可启动、基础路由可用、运行时文件与种子数据已生成。

Smoke tests: verify the app starts, basic routes work, runtime files are
created and seed data is written idempotently.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    """``GET /health`` 应返回 200 与状态 ok。

    ``GET /health`` should return 200 with status ok.
    """
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["time"]


def test_root_redirects(client: TestClient) -> None:
    """``GET /`` 应 302 重定向到 ``/counter``。

    ``GET /`` should 302-redirect to ``/counter``.
    """
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/counter"


def test_runtime_files_created(client: TestClient, data_dir: str) -> None:
    """启动后应生成 config.json 与 data/restaurant.db。

    After startup, ``config.json`` and ``data/restaurant.db`` should exist.
    """
    assert os.path.exists(os.path.join(data_dir, "config.json"))
    assert os.path.exists(os.path.join(data_dir, "data", "restaurant.db"))


def test_seed_idempotent(db_session) -> None:
    """重复调用 ``seed_if_needed`` 不应重复写入数据。

    Calling ``seed_if_needed`` repeatedly must not duplicate seed data.
    """
    from sqlalchemy import func, select

    from app.models import Category, Dish
    from app.seed import seed_if_needed

    seed_if_needed(db_session)
    first_categories = db_session.scalar(select(func.count()).select_from(Category))
    first_dishes = db_session.scalar(select(func.count()).select_from(Dish))

    seed_if_needed(db_session)
    second_categories = db_session.scalar(select(func.count()).select_from(Category))
    second_dishes = db_session.scalar(select(func.count()).select_from(Dish))

    assert first_categories == 4
    assert first_dishes == second_dishes
    assert first_categories == second_categories
