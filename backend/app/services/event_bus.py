"""进程内异步事件总线模块。

In-process asynchronous event bus module.

设计目标 / Design goals:
1. 线程安全：FastAPI 的同步端点在线程池中执行，需要能从中发布事件；
   Thread-safe: FastAPI sync endpoints run in a thread pool and must be able
   to publish events from there.
2. 事件循环桥接：发布方可能不在事件循环线程，因此统一通过
   ``loop.call_soon_threadsafe`` 把投递动作调度回事件循环；
   Loop bridging: publishers may live outside the event-loop thread, so the
   delivery is always scheduled back onto the loop via
   ``loop.call_soon_threadsafe``.
3. 无 loop / 无订阅者时静默降级，仅记录英文 debug 日志。
   Graceful degradation when there is no loop / no subscriber, logging only an
   English debug message.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 事件名：订单创建 / Event name: order created
EVENT_ORDER_CREATED = "order.created"
# 事件名：订单状态变更 / Event name: order status changed
EVENT_ORDER_STATUS_CHANGED = "order.status_changed"
# 事件名：订单明细状态变更 / Event name: order item status changed
EVENT_ORDER_ITEM_STATUS_CHANGED = "order.item_status_changed"
# 事件名：心跳 / Event name: heartbeat
EVENT_HEARTBEAT = "heartbeat"


@dataclass(frozen=True)
class Event:
    """事件载荷数据类。

    Event payload dataclass.

    :param name: 事件名 / event name
    :param data: 事件数据字典 / event data dict
    """

    # 事件名 / Event name
    name: str
    # 事件数据 / Event data
    data: Dict[str, Any] = field(default_factory=dict)


class Subscription:
    """订阅对象，持有用于接收事件的异步队列。

    A subscription object holding the async queue that receives events.
    """

    def __init__(self, queue: "asyncio.Queue[Event]") -> None:
        """构造订阅对象。

        Build a subscription object.

        :param queue: 接收事件的异步队列 / async queue receiving events
        """
        # 接收事件的队列 / Queue receiving events
        self.queue: "asyncio.Queue[Event]" = queue


class EventBus:
    """线程安全的进程内事件总线。

    A thread-safe in-process event bus.

    - ``subscribe`` 在首次调用时惰性捕获当前正在运行的事件循环；
      ``subscribe`` lazily captures the currently running event loop.
    - ``publish`` 可在任意线程调用，内部把投递调度回事件循环；
      ``publish`` may be called from any thread and schedules delivery back
      onto the event loop.
    """

    def __init__(self) -> None:
        """初始化事件总线。

        Initialize the event bus.
        """
        # 保护订阅者列表与事件循环引用的互斥锁
        # Mutex guarding the subscriber list and the loop reference
        self._lock = threading.Lock()
        # 当前订阅者列表 / Current subscriber list
        self._subscriptions: List[Subscription] = []
        # 主事件循环（惰性捕获或显式设置）/ Main event loop (lazy or explicit)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: Optional[asyncio.AbstractEventLoop]) -> None:
        """显式注册事件循环。

        Explicitly register the event loop.

        :param loop: 目标事件循环，None 表示清除 / target loop, None clears it
        """
        with self._lock:
            self._loop = loop
        logger.debug("Event bus loop set: %s", loop)

    def subscribe(self) -> Subscription:
        """订阅事件，返回带队列的订阅对象。

        Subscribe to events and return a subscription carrying a queue.

        若在事件循环中调用，则惰性捕获该循环，使后续同步线程的发布能投递进来。
        When called inside an event loop, the loop is lazily captured so later
        publishes from sync threads can be delivered.

        :return: 订阅对象 / subscription object
        """
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        with self._lock:
            if running_loop is not None:
                self._loop = running_loop
            subscription = Subscription(asyncio.Queue())
            self._subscriptions.append(subscription)
            count = len(self._subscriptions)
        logger.debug("Subscriber added, total=%s", count)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        """取消订阅。

        Unsubscribe the given subscription.

        :param subscription: 待移除的订阅对象 / subscription to remove
        """
        with self._lock:
            if subscription in self._subscriptions:
                self._subscriptions.remove(subscription)
                count = len(self._subscriptions)
            else:
                count = len(self._subscriptions)
        logger.debug("Subscriber removed, total=%s", count)

    def subscriber_count(self) -> int:
        """返回当前订阅者数量。

        Return the current number of subscribers.

        :return: 订阅者数量 / subscriber count
        """
        with self._lock:
            return len(self._subscriptions)

    def publish(self, event_name: str, data: Dict[str, Any]) -> None:
        """向所有订阅者广播事件（同步可调用）。

        Broadcast an event to all subscribers (callable from sync code).

        :param event_name: 事件名 / event name
        :param data: 事件数据字典 / event data dict
        """
        with self._lock:
            subscriptions = list(self._subscriptions)
            loop = self._loop

        if not subscriptions:
            logger.debug("No subscribers, skip publishing event=%s", event_name)
            return
        if loop is None or loop.is_closed():
            logger.debug(
                "No usable event loop, skip publishing event=%s subscribers=%s",
                event_name,
                len(subscriptions),
            )
            return

        event = Event(name=event_name, data=data)
        for subscription in subscriptions:
            try:
                loop.call_soon_threadsafe(subscription.queue.put_nowait, event)
            except RuntimeError:
                # 事件循环已关闭等异常，忽略即可，不影响发布方
                # Loop already closed or similar; ignore so publishers never fail
                logger.debug("Failed to schedule event=%s, loop unavailable", event_name)

    def reset(self) -> None:
        """清空所有订阅者与事件循环引用（测试用）。

        Clear all subscribers and the loop reference (for tests).
        """
        with self._lock:
            self._subscriptions.clear()
            self._loop = None
        logger.debug("Event bus reset")


# 全局事件总线单例 / Global event bus singleton
event_bus = EventBus()

# 对外导出清单 / Public export list
__all__ = [
    "EVENT_ORDER_CREATED",
    "EVENT_ORDER_STATUS_CHANGED",
    "EVENT_ORDER_ITEM_STATUS_CHANGED",
    "EVENT_HEARTBEAT",
    "Event",
    "Subscription",
    "EventBus",
    "event_bus",
]
