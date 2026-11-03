# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（one-folder 单目录模式）。

PyInstaller build configuration (one-folder mode).

为什么用 one-folder 而不是 one-file：
- one-file 每次启动都要把内容解压到临时目录，首次启动慢，且前端静态资源定位复杂；
- one-folder 启动快，可执行文件与依赖、前端资源同目录，路径解析稳定（见 ``app/paths.py``）。

Why one-folder instead of one-file:
- one-file unpacks into a temp directory on every launch (slow first start) and
  complicates locating the bundled frontend assets;
- one-folder starts fast and keeps the executable, dependencies and frontend
  assets in one directory, which ``app/paths.py`` resolves reliably.

打包命令 / Build command::

    pyinstaller --clean --noconfirm restaurant-ordering-system.spec
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

# SPECPATH 由 PyInstaller 注入，指向本 spec 文件所在目录（即项目根）
# SPECPATH is injected by PyInstaller and points to this spec file's directory
# (i.e. the project root).
PROJECT_ROOT = Path(SPECPATH).resolve()
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# 一并打进产物的资源文件 / Resource files bundled into the artifact.
# 目标路径 "frontend" 与 ``app/paths.py`` 中 frozen 模式下的
# ``<_MEIPASS>/frontend`` 保持一致。
# The destination "frontend" matches ``<_MEIPASS>/frontend`` in frozen mode,
# as expected by ``app/paths.py``.
datas = [
    (str(FRONTEND_DIR), "frontend"),
]

# 运行时动态导入、静态分析无法发现的模块必须显式声明，否则打包后会报
# ModuleNotFoundError / Modules imported dynamically at runtime are invisible to
# static analysis and must be declared explicitly, otherwise the frozen app
# raises ModuleNotFoundError.
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "anyio._backends._asyncio",
]

# escpos 的打印机后端（usb/cups/lp/file）与能力表均为动态导入
# escpos printer backends (usb/cups/lp/file) and capabilities are imported dynamically
hiddenimports += collect_submodules("escpos")
# uvicorn 的子模块数量多且多为动态选择，统一收集更稳妥
# uvicorn picks many submodules dynamically; collecting them all is safer
hiddenimports += collect_submodules("uvicorn")

# 明确排除与运行无关的大体积/干扰包（测试框架、打包器自身、GUI 库）
# Explicitly exclude irrelevant packages (test frameworks, the packager itself, GUI libs)
excludes = [
    "tkinter",
    "pytest",
    "_pytest",
    "PyInstaller",
    "IPython",
    "notebook",
]

a = Analysis(  # noqa: F821 - Analysis is injected by PyInstaller
    [str(BACKEND_DIR / "run.py")],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)  # noqa: F821 - PYZ is injected by PyInstaller

exe = EXE(  # noqa: F821 - EXE is injected by PyInstaller
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="restaurant-ordering-system",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX 压缩在 macOS 上通常不可用，且可能触发杀软误报，故关闭
    # UPX is usually unavailable on macOS and may trigger AV false positives
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(  # noqa: F821 - COLLECT is injected by PyInstaller
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="restaurant-ordering-system",
)
