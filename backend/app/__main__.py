"""``python -m app`` 入口模块。

Entry module for ``python -m app``.
"""

from __future__ import annotations

import sys

from .launcher import main

# 执行启动器并返回退出码 / Run the launcher and return its exit code
if __name__ == "__main__":
    sys.exit(main())
