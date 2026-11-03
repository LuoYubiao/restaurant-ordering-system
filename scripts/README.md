# scripts 打包与运维脚本目录

存放打包、发布与日常运维脚本。

## 一键打包

| 文件 | 平台 | 用法 |
| --- | --- | --- |
| [build.sh](file:///Users/yubiao/Develop/github_home/restaurant-ordering-system/scripts/build.sh) | macOS / Linux | `bash scripts/build.sh` |
| [build.bat](file:///Users/yubiao/Develop/github_home/restaurant-ordering-system/scripts/build.bat) | Windows | `scripts\build.bat` |

脚本会依次完成：

1. 优先使用 `backend/.venv` 中的 Python（不存在则回退到系统 `python3`/`python`）执行 PyInstaller；
2. 按项目根目录的 `restaurant-ordering-system.spec` 执行 **one-folder（单目录）** 打包；
3. 校验产物中可执行文件与 `_internal/frontend/counter/index.html` 是否存在；
4. 在 `dist/` 下生成 zip 分发包：
   - macOS / Linux：`dist/restaurant-ordering-system-macos.zip`
   - Windows：`dist/restaurant-ordering-system-windows.zip`

产物结构（以 macOS 为例）：

```
dist/restaurant-ordering-system/
├── restaurant-ordering-system        可执行文件（Windows 为 .exe），双击即启动
└── _internal/                        PyInstaller 运行时依赖与只读资源
    ├── frontend/                     前端页面与静态资源（含本地 Vue）
    │   ├── counter/ kitchen/ admin/ settings/
    │   └── static/css|js|vendor/
    └── ...                           第三方库
```

首次启动后，可执行文件同级目录会自动生成 `data/`、`logs/`、`printed/` 与 `config.json`，
这些是运行时可写数据，不包含在产物里（详见 `app/paths.py`）。

## 为什么用 one-folder 而不是 one-file

- one-file 每次启动都要把内容解压到临时目录，首次启动慢，且前端静态资源定位复杂；
- one-folder 启动快，可执行文件与依赖、前端资源同目录，路径解析稳定。

## 运行时路径区分逻辑

| 模式 | 数据目录（data/logs/printed/config.json） | 只读资源（frontend 等） |
| --- | --- | --- |
| 打包运行 | 可执行文件所在目录 | PyInstaller 解包目录 `_internal/` |
| 源码运行 | 项目根目录 | 项目根目录 |

## 打包配置说明

打包配置为项目根目录的 [restaurant-ordering-system.spec](file:///Users/yubiao/Develop/github_home/restaurant-ordering-system/restaurant-ordering-system.spec)：

- 入口脚本：`backend/run.py`；
- `datas`：将整个 `frontend/` 目录打包到 `_internal/frontend`，与 `app/paths.py` 的 frozen 分支对应；
- `hiddenimports`：显式声明 uvicorn / escpos / sqlalchemy 方言等运行时动态导入的模块；
- `excludes`：排除 `tkinter`、`pytest`、`PyInstaller` 等与运行无关的包以减小体积。
