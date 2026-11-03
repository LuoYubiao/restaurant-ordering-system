"""开箱即用启动器模块。

Ready-to-run launcher module.

负责端口探测、数据库初始化、控制台横幅与浏览器自动打开，并最终启动 uvicorn。
Handles free-port detection, database bootstrap, console banner, automatic
browser opening and finally starts uvicorn.
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from typing import List, Optional

from .config import get_config, load_config, update_config
from .database import init_db, session_scope
from .logging_config import setup_logging
from .main import app
from .paths import ensure_runtime_dirs
from .seed import seed_if_needed
from .services.printer_service import display_width

logger = logging.getLogger(__name__)

# 默认监听地址 / Default bind host
DEFAULT_HOST = "0.0.0.0"
# 默认起始端口 / Default starting port
DEFAULT_PORT = 8000
# 端口探测的最大尝试次数 / Max attempts when probing a free port
PORT_ATTEMPTS = 20


def find_free_port(start: int = DEFAULT_PORT, host: str = DEFAULT_HOST, attempts: int = PORT_ATTEMPTS) -> int:
    """从 ``start`` 起查找一个可用端口。

    Find a free port starting from ``start``.

    :param start: 起始端口 / starting port
    :param host: 绑定地址 / bind host
    :param attempts: 最大尝试次数 / max attempts
    :return: 可用端口号 / available port number
    :raises RuntimeError: 未找到可用端口 / when no free port is found
    """
    for offset in range(attempts):
        port = start + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                logger.info("Free port found: %s", port)
                return port
            except OSError:
                logger.info("Port %s is busy, trying next", port)
                continue
    raise RuntimeError(f"No free port found from {start} within {attempts} attempts")


def get_lan_ip() -> str:
    """获取本机局域网 IP 地址。

    Get the local LAN IP address. Falls back to ``127.0.0.1`` on failure.

    :return: 局域网 IP / LAN IP
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不真正发送数据，仅用于获取出口 IP / Does not send data; only resolves the outbound IP
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        logger.warning("Failed to detect LAN IP, falling back to 127.0.0.1")
        return "127.0.0.1"
    finally:
        sock.close()


def open_browser(url: str) -> None:
    """在默认浏览器中打开指定地址。

    Open the given URL in the default browser.

    :param url: 目标地址 / target URL
    """
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001 - browser opening must never crash startup
        logger.exception("Failed to open browser for %s", url)


def open_browser_when_ready(
    port: int,
    host: str = "127.0.0.1",
    timeout: float = 30.0,
    interval: float = 0.3,
) -> None:
    """等待服务端口真正可连接后，再打开浏览器到柜台点菜页。

    Wait until the server port is actually accepting connections, then open the
    browser on the counter ordering page. Opening too early (before uvicorn has
    bound the socket, e.g. while the first-run database is still initializing)
    would show a "connection refused" page to the user.

    :param port: 服务端口 / server port
    :param host: 探测地址 / probe host
    :param timeout: 最长等待秒数 / max seconds to wait
    :param interval: 探测间隔秒数 / probe interval in seconds
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=interval):
                logger.info("Server is ready, opening browser on port %s", port)
                open_browser(f"http://127.0.0.1:{port}/")
                return
        except OSError:
            time.sleep(interval)
    logger.warning("Server not ready within %.0fs, skipping browser open", timeout)


def print_banner(port: int, shop_name: str) -> None:
    """打印启动横幅（框线宽度自适应中文宽度）。

    Print the startup banner (box width adapts to Chinese display width).

    :param port: 服务端口 / server port
    :param shop_name: 店铺名称 / shop name
    """
    lan_ip = get_lan_ip()
    lines = [
        f"  {shop_name} 点菜系统已启动",
        f"  柜台点菜：http://127.0.0.1:{port}/counter",
        f"  厨房看板：http://{lan_ip}:{port}/kitchen",
        f"  菜品管理：http://{lan_ip}:{port}/admin",
        f"  系统设置：http://{lan_ip}:{port}/settings",
        "  关闭此窗口即停止服务",
    ]
    width = max(display_width(line) for line in lines)
    border = "=" * width
    print(border)
    for line in lines:
        print(line)
    print(border)


def _parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    """解析命令行参数。

    Parse command line arguments.

    :param argv: 参数列表 / argument list
    :return: 解析结果 / parsed namespace
    """
    parser = argparse.ArgumentParser(prog="app", description="餐饮小店点菜系统后端")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址 Bind host")
    parser.add_argument("--port", type=int, default=None, help="监听端口 Bind port")
    parser.add_argument(
        "--no-browser", action="store_true", help="不自动打开浏览器 Do not open browser"
    )
    parser.add_argument("--reload", action="store_true", help="开发模式热重载 Enable auto-reload")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """启动器主入口。

    Main launcher entry point.

    :param argv: 命令行参数（默认取 ``sys.argv[1:]``）/ CLI args (defaults to ``sys.argv[1:]``)
    :return: 进程退出码 / process exit code
    """
    args = _parse_args(argv)

    ensure_runtime_dirs()
    setup_logging()
    cfg = load_config()

    if args.port is None:
        port = find_free_port(cfg.serverPort, host=args.host)
        if port != cfg.serverPort:
            logger.info("Updating config serverPort %s -> %s", cfg.serverPort, port)
            cfg = update_config({"serverPort": port})
    else:
        port = args.port

    os.environ["ROS_RUNNING_PORT"] = str(port)

    init_db()
    with session_scope() as db:
        seed_if_needed(db)

    print_banner(port, cfg.shopName)

    if not args.no_browser:
        threading.Thread(
            target=open_browser_when_ready, args=(port,), daemon=True
        ).start()

    logger.info("Starting uvicorn on %s:%s (reload=%s)", args.host, port, args.reload)
    import uvicorn

    if args.reload:
        uvicorn.run("app.main:app", host=args.host, port=port, log_level="info", reload=True)
    else:
        uvicorn.run(app, host=args.host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
