# .github/workflows CI/CD 工作流目录

存放 GitHub Actions 工作流定义，用于在云端产出各平台分发包。

## 现有工作流

| 文件 | 运行器 | 产物 | 触发方式 |
| --- | --- | --- | --- |
| [build-packages.yml](file:///Users/yubiao/Develop/github_home/restaurant-ordering-system/.github/workflows/build-packages.yml) | `macos-latest`、`windows-latest`（双 job 并行） | `restaurant-ordering-system-macos.zip`、`restaurant-ordering-system-windows.zip` | 手动 `workflow_dispatch`；推送 `v*` tag |

## 为什么必须分平台构建

PyInstaller 不支持交叉编译：可执行文件的引导程序与 Python 运行时都是平台相关的二进制，无法在 macOS 上生成 `.exe`，反之亦然。因此工作流拆成两个 job，各自在原生运行器上执行对应的打包脚本：

| 平台 | 运行器 | 脚本 | 产物 |
| --- | --- | --- | --- |
| macOS（arm64） | `macos-latest` | `bash scripts/build.sh` | `dist/restaurant-ordering-system-macos.zip` |
| Windows（x64） | `windows-latest` | `scripts\build.bat` | `dist/restaurant-ordering-system-windows.zip` |

两个 job 相互独立、并行执行，单个平台失败不会影响另一个平台。

> 不使用 `matrix` 的原因：GitHub Actions 的 `shell` 键不接受表达式，`matrix` 上下文在该处不可用，会报 `Unrecognized named-value: 'matrix'`。拆成两个 job 后 `shell` 保持为字面量。

## 与本地构建的差异

- 运行器上不存在 `backend/.venv`，脚本会自动回退到 `setup-python` 提供的解释器；
- 依赖由 `pip install -r backend/requirements.txt` 安装，与本地同一份锁定版本；
- 产物通过 `actions/upload-artifact` 上传，在 Actions 运行详情页下载，默认保留 30 天。

## 备注

`macos-latest` 当前指向 Apple Silicon（arm64）运行器，产物为 arm64 架构。若需同时支持 Intel Mac，可在矩阵中追加 `macos-13`（x86_64）并把产物名区分为 `-macos-x64.zip`。
