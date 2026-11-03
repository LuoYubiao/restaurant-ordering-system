"""实时事件流接口路由（SSE）。

Realtime event stream API router (Server-Sent Events).

通过 SSE 把订单创建 / 状态变更等事件实时推送给柜台与厨房页面。
Pushes order events (creation, status changes, ...) to counter and kitchen pages
in realtime via SSE.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, AsyncIterator, Dict

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..services import event_bus

logger = logging.getLogger(__name__)

# 事件流路由 / Event stream router
router = APIRouter(tags=["stream"])

# 环境变量：心跳间隔秒数 / Env var: heartbeat interval in seconds
ENV_HEARTBEAT_SECONDS = "ROS_SSE_HEARTBEAT_SECONDS"
# 默认心跳间隔秒数 / Default heartbeat interval in seconds
DEFAULT_HEARTBEAT_SECONDS = 15.0
# 连接建立事件名 / Event name for connection established
EVENT_CONNECTED = "connected"


def _heartbeat_seconds() -> float:
    """读取心跳间隔（秒），支持环境变量覆盖。

    Read the heartbeat interval in seconds, overridable via env var.

    :return: 心跳间隔秒数 / heartbeat interval in seconds
    """
    raw = os.environ.get(ENV_HEARTBEAT_SECONDS)
    if raw is None or not raw.strip():
        return DEFAULT_HEARTBEAT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "Invalid %s=%s, using default %s",
            ENV_HEARTBEAT_SECONDS,
            raw,
            DEFAULT_HEARTBEAT_SECONDS,
        )
        return DEFAULT_HEARTBEAT_SECONDS
    return value if value > 0 else DEFAULT_HEARTBEAT_SECONDS


def _format_sse(event_name: str, data: Dict[str, Any]) -> str:
    """按 SSE 规范格式化一条事件消息。

    Format a single SSE message following the spec.

    :param event_name: 事件名 / event name
    :param data: 事件数据 / event data
    :return: SSE 文本（以空行结尾）/ SSE text (ending with a blank line)
    """
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _event_generator(
    subscription: event_bus.Subscription, heartbeat: float
) -> AsyncIterator[str]:
    """SSE 事件生成器：先发连接事件，再持续推送事件与心跳。

    SSE event generator: emit a connection event first, then keep pushing
    events and heartbeats.

    :param subscription: 事件总线订阅对象 / event bus subscription
    :param heartbeat: 心跳间隔秒数 / heartbeat interval in seconds
    :return: 异步字符串生成器 / async string generator
    """
    try:
        # 连接建立事件 / Connection established event
        yield _format_sse(EVENT_CONNECTED, {"time": datetime.now().isoformat()})
        while True:
            try:
                event = await asyncio.wait_for(
                    subscription.queue.get(), timeout=heartbeat
                )
            except TimeoutError:
                # 空闲超时：发送心跳保活 / Idle timeout: send a keep-alive heartbeat
                yield _format_sse(
                    event_bus.EVENT_HEARTBEAT, {"time": datetime.now().isoformat()}
                )
                continue
            yield _format_sse(event.name, event.data)
    except asyncio.CancelledError:
        # 客户端断开，向上抛出以完成清理 / Client disconnected; re-raise after cleanup
        logger.debug("SSE stream cancelled by client")
        raise
    finally:
        # 无论正常结束还是断开，都要取消订阅释放资源
        # Always unsubscribe to release resources, on both normal end and disconnect
        event_bus.event_bus.unsubscribe(subscription)
        logger.info(
            "SSE client disconnected, remaining subscribers=%s",
            event_bus.event_bus.subscriber_count(),
        )


@router.get("/orders/stream")
async def order_stream(request: Request) -> StreamingResponse:
    """订单事件实时推送（SSE）。

    Realtime order event stream (SSE).

    :param request: 请求对象 / request object
    :return: SSE 流式响应 / SSE streaming response
    """
    heartbeat = _heartbeat_seconds()
    subscription = event_bus.event_bus.subscribe()
    logger.info(
        "SSE client connected, heartbeat=%ss subscribers=%s",
        heartbeat,
        event_bus.event_bus.subscriber_count(),
    )
    return StreamingResponse(
        _event_generator(subscription, heartbeat),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
