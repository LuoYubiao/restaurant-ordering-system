"""事件总线与 SSE 实时流测试。

Tests for the event bus and the SSE realtime stream.

覆盖事件总线订阅/发布、无订阅者发布、SSE 端点契约（connected/heartbeat）
以及下单后通过 SSE 收到 ``order.created`` 事件。
Covers bus subscribe/publish, publishing without subscribers, the SSE endpoint
contract (connected / heartbeat) and receiving ``order.created`` over SSE after
placing an order.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Dish
from app.services import event_bus


@pytest.fixture(autouse=True)
def _clean_event_bus():
    """每个测试前后清空事件总线。

    Reset the event bus before and after each test.
    """
    event_bus.event_bus.reset()
    yield
    event_bus.event_bus.reset()


class _SseReader:
    """SSE 后台读取器：在独立线程中解析事件，便于断言与超时。

    A background SSE reader that parses events in a separate thread so tests can
    assert on them without blocking forever.
    """

    def __init__(self, response) -> None:
        """启动后台读取线程。

        Start the background reading thread.

        :param response: httpx 流式响应 / httpx streaming response
        """
        # 已解析事件列表 [(event, data)] / parsed events list
        self._events: list[tuple[str, str]] = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run, args=(response,), daemon=True
        )
        self._thread.start()

    def _run(self, response) -> None:
        """线程主体：逐行解析 SSE 事件块。

        Thread body: parse SSE event blocks line by line.

        :param response: httpx 流式响应 / httpx streaming response
        """
        current: dict[str, str | None] = {"event": None, "data": None}
        try:
            for line in response.iter_lines():
                if line.startswith("event: "):
                    current["event"] = line[len("event: ") :]
                elif line.startswith("data: "):
                    current["data"] = line[len("data: ") :]
                elif line == "":
                    if current["event"] is not None:
                        with self._lock:
                            self._events.append((current["event"], current["data"] or ""))
                    current["event"] = None
                    current["data"] = None
        except Exception:  # noqa: BLE001 - stream closed during teardown is fine
            return

    def wait_for(self, predicate, timeout: float = 5.0) -> list[tuple[str, str]]:
        """等待直到满足条件或超时。

        Wait until the predicate holds or the timeout elapses.

        :param predicate: 接收事件快照返回布尔值 / predicate over an events snapshot
        :param timeout: 最长等待秒数 / max wait in seconds
        :return: 事件快照 / events snapshot
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                snapshot = list(self._events)
            if predicate(snapshot):
                return snapshot
            time.sleep(0.01)
        with self._lock:
            return list(self._events)

    def events(self) -> list[tuple[str, str]]:
        """返回当前已解析的事件快照。

        Return the current snapshot of parsed events.

        :return: 事件快照 / events snapshot
        """
        with self._lock:
            return list(self._events)


def test_event_bus_publish_subscribe() -> None:
    """订阅后发布，订阅者队列能收到对应事件名与数据。

    After subscribing, publishing delivers the event name and data to the queue.
    """
    loop = asyncio.new_event_loop()
    try:
        event_bus.event_bus.set_loop(loop)
        subscription = event_bus.event_bus.subscribe()
        assert event_bus.event_bus.subscriber_count() == 1

        event_bus.event_bus.publish(
            event_bus.EVENT_ORDER_CREATED, {"id": 1, "orderNo": "20260101-0001"}
        )
        event = loop.run_until_complete(
            asyncio.wait_for(subscription.queue.get(), timeout=1)
        )
        assert event.name == event_bus.EVENT_ORDER_CREATED
        assert event.data == {"id": 1, "orderNo": "20260101-0001"}
    finally:
        event_bus.event_bus.reset()
        loop.close()


def test_event_bus_publish_without_subscribers() -> None:
    """无订阅者时发布不应报错。

    Publishing without subscribers must not raise.
    """
    event_bus.event_bus.reset()
    assert event_bus.event_bus.subscriber_count() == 0
    # 不抛异常即为通过 / Passing means no exception is raised
    event_bus.event_bus.publish(event_bus.EVENT_ORDER_CREATED, {"id": 1})


def test_sse_endpoint_contract(client: TestClient, monkeypatch) -> None:
    """SSE 端点契约：先发 connected，随后发送 heartbeat。

    SSE endpoint contract: emits ``connected`` first, then ``heartbeat``.
    """
    monkeypatch.setenv("ROS_SSE_HEARTBEAT_SECONDS", "0.05")

    with client.stream("GET", "/api/orders/stream") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers["cache-control"] == "no-cache"
        assert resp.headers["x-accel-buffering"] == "no"

        reader = _SseReader(resp)
        events = reader.wait_for(
            lambda snapshot: any(name == "connected" for name, _ in snapshot)
            and any(name == "heartbeat" for name, _ in snapshot),
            timeout=5.0,
        )

    names = [name for name, _ in events]
    assert "connected" in names
    assert "heartbeat" in names

    connected_payload = json.loads(next(data for name, data in events if name == "connected"))
    assert "time" in connected_payload


def test_sse_receives_order_created(client: TestClient, db_session, monkeypatch) -> None:
    """下单后可通过 SSE 收到 order.created 事件。

    After placing an order, the ``order.created`` event is received over SSE.
    """
    monkeypatch.setenv("ROS_SSE_HEARTBEAT_SECONDS", "5")

    db_session.commit()
    dish = db_session.scalars(select(Dish).order_by(Dish.Id)).first()

    with client.stream("GET", "/api/orders/stream") as resp:
        reader = _SseReader(resp)
        reader.wait_for(
            lambda snapshot: any(name == "connected" for name, _ in snapshot),
            timeout=5.0,
        )

        create_resp = client.post(
            "/api/orders",
            json={
                "tableNo": "B2",
                "diningType": "dine_in",
                "items": [{"dishId": dish.Id, "quantity": 1}],
            },
        )
        assert create_resp.status_code == 201

        events = reader.wait_for(
            lambda snapshot: any(
                name == event_bus.EVENT_ORDER_CREATED for name, _ in snapshot
            ),
            timeout=5.0,
        )

    created = [data for name, data in events if name == event_bus.EVENT_ORDER_CREATED]
    assert created, "未通过 SSE 收到 order.created 事件"

    payload = json.loads(created[0])
    assert payload["status"] == "pending"
    assert payload["items"][0]["dishName"] == dish.Name
