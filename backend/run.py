"""源码模式启动入口（双击/命令行均可运行）。

Source-mode entry point (runnable by double-click or command line).

等价于 ``python -m app``。
Equivalent to ``python -m app``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 backend 目录在导入路径中 / Ensure the backend directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.launcher import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
