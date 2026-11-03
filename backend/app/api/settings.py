"""系统设置接口路由。

Settings API router.

提供系统配置的读取与热更新、测试打印，以及运行状态（端口、局域网地址等）
查询，供系统设置页使用。
Provides endpoints to read and hot-update the system settings, run a test
print, and query runtime status (port, LAN URLs, etc.) for the settings page.
"""

from __future__ import annotations

import logging
import os
from typing import Dict

from fastapi import APIRouter, HTTPException, status

from ..config import AppConfig, get_config, update_config
from ..paths import get_data_dir, get_printed_dir
from ..schemas.settings import (
    PrinterSettings,
    SettingsOut,
    SettingsStatus,
    SettingsUpdate,
    SettingsUpdateResult,
    TestPrintResult,
)
from ..services import printer_service
from ..version import __version__

logger = logging.getLogger(__name__)

# 系统设置接口路由 / Settings router
router = APIRouter(tags=["settings"])

# 环境变量：运行中的实际端口 / Env var holding the actual running port
ENV_RUNNING_PORT = "ROS_RUNNING_PORT"

# 页面相对路径（用于拼接访问地址）/ Page paths used to build access URLs
_PAGE_PATHS = {
    "counter": "/counter",
    "kitchen": "/kitchen",
    "admin": "/admin",
    "settings": "/settings",
}


def _to_settings_out(cfg: AppConfig) -> SettingsOut:
    """把配置对象转换为设置输出模型。

    Convert the config object into the settings output schema.

    :param cfg: 应用配置 / application config
    :return: 设置输出模型 / settings output schema
    """
    return SettingsOut(
        shopName=cfg.shopName,
        serverPort=cfg.serverPort,
        printCounterTicket=cfg.printCounterTicket,
        printKitchenTicket=cfg.printKitchenTicket,
        printer=PrinterSettings(**cfg.printer.model_dump()),
    )


def _validate_merged_printer(printer: Dict[str, object]) -> None:
    """校验合并后的打印机配置，非法时抛出 400。

    Validate the merged printer configuration, raising 400 when it is illegal.
    This catches cases the per-request schema cannot see (e.g. switching to
    network mode while the stored host is blank).

    :param printer: 合并后的打印机配置字典 / merged printer config dict
    :raises HTTPException: 配置非法时 / when the config is illegal
    """
    mode = str(printer.get("mode") or "mock").lower()
    if mode == "network":
        if not str(printer.get("host") or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="网口模式下打印机 IP/主机名不能为空",
            )
        port = printer.get("port")
        if not isinstance(port, int) or not (1 <= port <= 65535):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="网口打印机端口必须在 1-65535 之间",
            )
    elif mode == "usb":
        vendor_id = printer.get("usbVendorId")
        product_id = printer.get("usbProductId")
        if (
            not isinstance(vendor_id, int)
            or vendor_id <= 0
            or not isinstance(product_id, int)
            or product_id <= 0
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="USB 打印机必须填写正整数厂商 ID 与产品 ID",
            )
    elif mode != "mock":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的打印机模式：{mode}",
        )


@router.get("/settings", response_model=SettingsOut)
def read_settings() -> SettingsOut:
    """读取当前系统配置。

    Read the current system configuration.

    :return: 设置输出模型 / settings output schema
    """
    cfg = get_config()
    logger.info("Read settings, shopName=%s, printerMode=%s", cfg.shopName, cfg.printer.mode)
    return _to_settings_out(cfg)


@router.put("/settings", response_model=SettingsUpdateResult)
def update_settings(payload: SettingsUpdate) -> SettingsUpdateResult:
    """更新系统配置并即时生效（端口变更除外）。

    Update the system configuration. All settings take effect immediately via a
    printer hot-reload, except ``serverPort`` which requires a restart (reported
    through ``restartRequired``).

    :param payload: 设置更新输入 / settings update input
    :return: 更新后的设置及重启标记 / updated settings with the restart flag
    """
    # 仅合并请求中显式提供的字段 / Merge only fields explicitly present in the request
    patch = payload.model_dump(exclude_unset=True, exclude_none=True)
    old_cfg = get_config()

    # 校验合并后的打印机配置 / Validate the merged printer configuration
    merged_printer = {**old_cfg.printer.model_dump(), **(patch.get("printer") or {})}
    _validate_merged_printer(merged_printer)

    old_port = old_cfg.serverPort
    cfg = update_config(patch)
    # 让新配置立即生效（清空缓存连接）/ Apply immediately by clearing the cached connection
    printer_service.reload_printer()

    restart_required = "serverPort" in patch and patch["serverPort"] != old_port
    logger.info(
        "Settings updated, restartRequired=%s, printerMode=%s", restart_required, cfg.printer.mode
    )
    return SettingsUpdateResult(
        **_to_settings_out(cfg).model_dump(), restartRequired=restart_required
    )


def _failure_hint(raw_message: str) -> str:
    """把打印失败信息转换为带排查建议的中文提示。

    Turn a raw print failure message into a readable Chinese hint with
    troubleshooting suggestions.

    :param raw_message: 服务返回的原始失败信息 / raw failure message from the service
    :return: 带建议的中文提示 / Chinese hint with suggestions
    """
    lowered = (raw_message or "").lower()
    if "timeout" in lowered or "timed out" in lowered or "超时" in raw_message:
        return "连接打印机超时，请确认打印机已开机、IP 与端口正确、与本机在同一网络"
    if "refused" in lowered or "拒绝" in raw_message:
        return "打印机拒绝了连接，请确认打印机端口（常见为 9100）以及是否已开启 RAW/ESC-POS 打印服务"
    if "未配置" in raw_message or "缺少" in raw_message:
        return f"{raw_message}，请先在设置页补全打印机参数"
    return f"测试打印失败：{raw_message}，请确认打印机已开机并与本机在同一网络"


@router.post("/settings/test-print", response_model=TestPrintResult)
def test_print() -> TestPrintResult:
    """触发一次测试打印（任何异常都转为可读结果，绝不返回 500）。

    Trigger a test print. Any failure — including unexpected exceptions — is
    caught, logged in English and converted into a readable ``ok=false`` result;
    this endpoint never returns HTTP 500.

    :return: 测试打印结果 / test print result
    """
    mode = (get_config().printer.mode or "mock").lower()
    try:
        result = printer_service.test_print()
    except Exception as exc:  # noqa: BLE001 - the endpoint must never raise
        logger.exception("Test print raised an unexpected error, mode=%s", mode)
        return TestPrintResult(
            ok=False,
            message=f"测试打印失败：{exc}，请检查打印机连接与配置",
        )

    if result.ok:
        if mode == "mock":
            message = (
                "当前为模拟打印模式，未连接真实打印机。"
                f"测试小票已保存到 {get_printed_dir()} 目录"
            )
        else:
            message = "测试打印成功，请确认打印机已正常出纸"
        logger.info("Test print succeeded, mode=%s", mode)
        return TestPrintResult(ok=True, message=message)

    logger.error("Test print failed, mode=%s, reason=%s", mode, result.message)
    return TestPrintResult(ok=False, message=_failure_hint(result.message))


def _resolve_running_port(default_port: int) -> int:
    """解析当前运行端口。

    Resolve the current running port. Priority: the ``ROS_RUNNING_PORT``
    environment variable (written by the launcher) then the configured port.

    :param default_port: 回退端口（来自配置）/ fallback port from config
    :return: 运行端口 / running port
    """
    raw = os.environ.get(ENV_RUNNING_PORT)
    if raw:
        try:
            return int(raw)
        except ValueError:
            logger.warning("Invalid %s=%s, falling back to config port", ENV_RUNNING_PORT, raw)
    return default_port


def _resolve_lan_ip() -> str:
    """获取局域网 IP（延迟导入以避免循环依赖）。

    Resolve the LAN IP. The launcher is imported lazily to avoid a circular
    import (``app.launcher`` imports ``app.main`` which imports this router).

    :return: 局域网 IP / LAN IP (falling back to 127.0.0.1)
    """
    try:
        from ..launcher import get_lan_ip

        return get_lan_ip()
    except Exception:  # noqa: BLE001 - status must never fail
        logger.exception("Failed to resolve LAN IP, falling back to 127.0.0.1")
        return "127.0.0.1"


def _build_urls(host: str, port: int) -> Dict[str, str]:
    """根据主机与端口拼接各页面访问地址。

    Build page access URLs from the host and port.

    :param host: 主机（IP 或域名）/ host (IP or hostname)
    :param port: 端口 / port
    :return: 页面名到访问地址的映射 / mapping of page name to URL
    """
    base = f"http://{host}:{port}"
    return {name: f"{base}{path}" for name, path in _PAGE_PATHS.items()}


@router.get("/settings/status", response_model=SettingsStatus)
def get_status() -> SettingsStatus:
    """读取运行状态（端口、打印机模式、局域网地址、路径与版本）。

    Read runtime status: port, printer mode, LAN/localhost URLs, data and
    printed-directory paths, and the application version.

    :return: 运行状态模型 / runtime status schema
    """
    cfg = get_config()
    port = _resolve_running_port(cfg.serverPort)
    lan_ip = _resolve_lan_ip()
    printer_mode = (cfg.printer.mode or "mock").lower()
    logger.info("Read status, port=%s, printerMode=%s", port, printer_mode)
    return SettingsStatus(
        port=port,
        shopName=cfg.shopName,
        isMockPrinter=printer_mode == "mock",
        printerMode=printer_mode,
        lanUrls=_build_urls(lan_ip, port),
        localUrls=_build_urls("127.0.0.1", port),
        dbPath=str(get_data_dir() / "restaurant.db"),
        printedDir=str(get_printed_dir()),
        version=__version__,
    )
