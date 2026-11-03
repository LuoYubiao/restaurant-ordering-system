"""运行时路径解析模块。

Runtime path resolution module.

本模块统一处理「源码运行」与「PyInstaller 打包运行」两种模式下的路径问题，
并提供环境变量覆盖能力（主要用于测试隔离）。
This module resolves runtime paths for both source-run and PyInstaller-frozen
modes, and supports environment-variable overrides (mainly for test isolation).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 环境变量：覆盖运行时数据根目录 / Env var to override the runtime data root
ENV_DATA_DIR = "ROS_DATA_DIR"
# 环境变量：覆盖前端静态目录 / Env var to override the frontend directory
ENV_FRONTEND_DIR = "ROS_FRONTEND_DIR"


def is_frozen() -> bool:
    """判断当前是否处于 PyInstaller 打包运行模式。

    Return ``True`` when the process is running from a PyInstaller bundle.
    """
    return bool(getattr(sys, "frozen", False))


def get_base_dir() -> Path:
    """获取运行时数据根目录。

    打包运行时为可执行文件所在目录；源码运行时为项目根目录
    （即 ``backend`` 的上一级）。环境变量 ``ROS_DATA_DIR`` 可覆盖该值。

    Return the runtime data root directory. When frozen this is the directory
    containing the executable; in source mode it is the project root (the
    parent of the ``backend`` folder). ``ROS_DATA_DIR`` overrides the value.
    """
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        return Path(override).expanduser().resolve()
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # 源码模式：backend/app/paths.py -> parents[2] 即项目根
    # Source mode: backend/app/paths.py -> parents[2] is the project root.
    return Path(__file__).resolve().parents[2]


def get_bundle_dir() -> Path:
    """获取只读资源根目录。

    打包运行时为 PyInstaller 解包目录 ``sys._MEIPASS``；源码运行时为项目根目录。

    Return the read-only resource root. When frozen it is the PyInstaller
    extraction directory (``sys._MEIPASS``); in source mode it is the project
    root.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    """获取数据目录（SQLite 数据库所在目录）。

    Return the data directory where the SQLite database lives.
    """
    return get_base_dir() / "data"


def get_logs_dir() -> Path:
    """获取日志目录。

    Return the log directory.
    """
    return get_base_dir() / "logs"


def get_printed_dir() -> Path:
    """获取模拟打印输出目录（mock 模式的小票文本会写到这里）。

    Return the directory storing mock-printed ticket text files.
    """
    return get_base_dir() / "printed"


def get_config_path() -> Path:
    """获取本地配置文件 config.json 的完整路径。

    Return the full path of the local ``config.json`` file.
    """
    return get_base_dir() / "config.json"


def get_frontend_dir() -> Path:
    """获取前端目录。

    打包运行时为 ``bundle/frontend``；源码运行时为项目根目录下的 ``frontend``。
    环境变量 ``ROS_FRONTEND_DIR`` 可覆盖该值。

    Return the frontend directory. When frozen it is ``bundle/frontend``; in
    source mode it is ``frontend`` under the project root. ``ROS_FRONTEND_DIR``
    overrides the value.
    """
    override = os.environ.get(ENV_FRONTEND_DIR)
    if override:
        return Path(override).expanduser().resolve()
    if is_frozen():
        return get_bundle_dir() / "frontend"
    # 源码模式固定指向项目根目录下的 frontend（不受 ROS_DATA_DIR 影响）
    # Source mode always points to ``frontend`` under the project root,
    # independent of ROS_DATA_DIR.
    return Path(__file__).resolve().parents[2] / "frontend"


def ensure_runtime_dirs() -> None:
    """确保运行时目录存在（data / logs / printed）。

    Ensure the runtime directories exist (data / logs / printed).
    """
    for directory in (get_data_dir(), get_logs_dir(), get_printed_dir()):
        directory.mkdir(parents=True, exist_ok=True)
