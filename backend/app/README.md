# app 应用代码目录说明

后端应用的核心代码目录，各模块职责如下：

| 文件 / 目录 | 说明 |
| --- | --- |
| `main.py` | 装配 FastAPI 应用：生命周期、静态资源、页面路由、`/health`、全局异常处理 |
| `launcher.py` | 开箱即用启动器：端口探测、横幅、自动打开浏览器、启动 uvicorn |
| `__main__.py` | `python -m app` 入口 |
| `paths.py` | 运行时路径解析（区分源码运行与 PyInstaller 打包运行） |
| `config.py` | 本地配置读写（config.json，支持环境变量覆盖） |
| `logging_config.py` | 日志初始化（按天滚动文件 + 控制台） |
| `database.py` | SQLAlchemy 引擎、会话与基础工具 |
| `money.py` | 金额换算（分 <-> 元字符串） |
| `seed.py` | 初始种子数据（分类与示例菜品） |
| `version.py` | 版本号 |
| `models/` | ORM 数据模型与枚举 |
| `schemas/` | Pydantic 出入参模型 |
| `api/` | HTTP 接口路由 |
| `services/` | 业务服务层（含小票打印） |

## 约定

- 所有类、函数、方法均有中英文双语注释。
- 日志正文统一使用英文。
- 金额以「分」为单位的整数存储，对外返回两位小数字符串。
