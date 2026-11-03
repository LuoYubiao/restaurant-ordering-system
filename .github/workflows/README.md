# .github/workflows CI/CD 工作流目录

存放 GitHub Actions 工作流定义，用于在云端产出各平台分发包。

## 现有工作流

| 文件 | 运行器 | 产物 | 触发方式 |
| --- | --- | --- | --- |
| [build-windows.yml](file:///Users/yubiao/Develop/github_home/restaurant-ordering-system/.github/workflows/build-windows.yml) | `windows-latest` | `restaurant-ordering-system-windows.zip` | 手动 `workflow_dispatch`；推送 `v*` tag |

## 为什么 Windows 包只能由 CI 产出

PyInstaller 不支持交叉编译：`.exe` 的引导程序与 Python 运行时都是平台相关的二进制，无法在 macOS 上生成。因此 Windows 产物必须交由 `windows-latest` 运行器执行 [scripts/build.bat](file:///Users/yubiao/Develop/github_home/restaurant-ordering-system/scripts/build.bat) 产出。

macOS 包可直接在本机执行 `bash scripts/build.sh` 生成，无需上 CI。

## 与本地构建的差异

- 运行器上不存在 `backend/.venv`，`build.bat` 会自动回退到 `setup-python` 提供的 `python`；
- 依赖由 `pip install -r backend/requirements.txt` 安装，与本地同一份锁定版本；
- 产物通过 `actions/upload-artifact` 上传，在 Actions 运行详情页下载，默认保留 30 天。
