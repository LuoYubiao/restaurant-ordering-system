"""本地配置模块。

Local configuration module.

配置以 JSON 文件形式存放在运行时数据根目录（``config.json``），
使用 pydantic v2 模型进行校验，并支持环境变量覆盖（便于测试与部署）。
Configuration is stored as a JSON file (``config.json``) in the runtime data
root, validated with pydantic v2 models, and can be overridden via environment
variables (for tests and deployment).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from .paths import get_config_path

logger = logging.getLogger(__name__)

# 进程内配置缓存单例 / In-process cached config singleton
_cached_config: Optional["AppConfig"] = None


class PrinterConfig(BaseModel):
    """打印机配置模型。

    Printer configuration model.
    """

    # 打印机连接模式：mock（模拟）/ network（网口）/ usb（USB）
    # Printer mode: mock / network / usb
    mode: str = "mock"
    # 网口打印机 IP 地址 / Network printer IP address
    host: str = "192.168.1.200"
    # 网口打印机端口（ESC/POS 默认 9100）/ Network printer port (ESC/POS default 9100)
    port: int = 9100
    # USB 打印机厂商 ID / USB vendor id
    usbVendorId: Optional[int] = None
    # USB 打印机产品 ID / USB product id
    usbProductId: Optional[int] = None
    # 纸张宽度（毫米）：58 或 80 / Paper width in mm: 58 or 80
    paperWidth: int = 58


class AppConfig(BaseModel):
    """应用主配置模型。

    Main application configuration model.
    """

    # 店铺名称，用于小票抬头 / Shop name used on ticket headers
    shopName: str = "我的小店"
    # 服务监听端口 / Server listening port
    serverPort: int = 8000
    # 是否打印柜台小票 / Whether to print the counter ticket
    printCounterTicket: bool = True
    # 是否打印厨房小票 / Whether to print the kitchen ticket
    printKitchenTicket: bool = True
    # 打印机配置 / Printer configuration
    printer: PrinterConfig = PrinterConfig()


def _apply_env_overrides(cfg: AppConfig) -> AppConfig:
    """根据环境变量覆盖配置项。

    Apply environment-variable overrides onto the given config.

    :param cfg: 已加载的配置对象 / loaded config object
    :return: 覆盖后的配置对象 / config with overrides applied
    """
    if (value := os.environ.get("ROS_SHOP_NAME")) is not None:
        cfg.shopName = value
    if (value := os.environ.get("ROS_PORT")) is not None:
        try:
            cfg.serverPort = int(value)
        except ValueError:
            logger.warning("Invalid ROS_PORT=%s, keep default", value)
    if (value := os.environ.get("ROS_PRINTER_MODE")) is not None:
        cfg.printer.mode = value
    if (value := os.environ.get("ROS_PRINTER_HOST")) is not None:
        cfg.printer.host = value
    if (value := os.environ.get("ROS_PRINTER_PORT")) is not None:
        try:
            cfg.printer.port = int(value)
        except ValueError:
            logger.warning("Invalid ROS_PRINTER_PORT=%s, keep default", value)
    if (value := os.environ.get("ROS_PAPER_WIDTH")) is not None:
        try:
            cfg.printer.paperWidth = int(value)
        except ValueError:
            logger.warning("Invalid ROS_PAPER_WIDTH=%s, keep default", value)
    return cfg


def default_config() -> AppConfig:
    """构造默认配置（含环境变量覆盖）。

    Build a default config (with environment overrides applied).
    """
    return _apply_env_overrides(AppConfig())


def save_config(cfg: AppConfig) -> AppConfig:
    """原子地保存配置到 config.json 并返回保存后的对象。

    Atomically save the config to ``config.json`` and return the saved object.
    Writes to a temporary file first then replaces the target to avoid
    corruption.

    :param cfg: 待保存的配置对象 / config object to save
    :return: 传入的配置对象 / the same config object
    """
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = cfg.model_dump()
    # 先写临时文件再原子替换 / Write to a temp file, then atomically replace
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix="config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    except OSError:
        logger.exception("Failed to write config file: %s", path)
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
    logger.info("Config saved to %s", path)
    return cfg


def load_config() -> AppConfig:
    """读取配置；文件不存在时写入默认配置，文件损坏时回退默认。

    Load the config. If the file does not exist, a default config is written
    and returned. If the file is corrupted, fall back to the default config
    without crashing.

    :return: 配置对象 / config object
    """
    path: Path = get_config_path()
    if not path.exists():
        cfg = default_config()
        try:
            save_config(cfg)
        except OSError:
            logger.warning("Could not persist default config, using in-memory default")
        return cfg
    try:
        with path.open("r", encoding="utf-8") as fp:
            data: Any = json.load(fp)
        cfg = AppConfig.model_validate(data)
    except (json.JSONDecodeError, ValueError, OSError):
        logger.exception("Config file is invalid, falling back to defaults: %s", path)
        return _apply_env_overrides(AppConfig())
    return _apply_env_overrides(cfg)


def get_config() -> AppConfig:
    """获取进程内缓存的配置单例。

    Return the process-wide cached config singleton (loading it on first use).
    """
    global _cached_config
    if _cached_config is None:
        _cached_config = load_config()
    return _cached_config


def update_config(patch: dict) -> AppConfig:
    """合并部分字段并保存，同时刷新缓存（供设置页热更新使用）。

    Merge a partial patch into the current config, persist it and refresh the
    cache (used by the settings page for hot updates).

    :param patch: 待合并的字段字典 / dict of fields to merge
    :return: 更新后的配置对象 / updated config object
    """
    global _cached_config
    merged = get_config().model_dump()
    _deep_merge(merged, patch)
    cfg = AppConfig.model_validate(merged)
    _cached_config = save_config(cfg)
    return _cached_config


def _deep_merge(base: dict, patch: dict) -> None:
    """递归合并字典，``patch`` 中的值覆盖 ``base``。

    Recursively merge ``patch`` into ``base`` (patch wins).

    :param base: 被更新的字典 / dict to be updated in place
    :param patch: 补丁字典 / patch dict
    """
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def reset_config_cache() -> None:
    """清空配置缓存（测试用）。

    Reset the in-process config cache (for tests).
    """
    global _cached_config
    _cached_config = None
