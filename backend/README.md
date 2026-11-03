# backend 后端目录说明

本目录是「餐饮小店点菜系统」的后端服务，基于 Python + FastAPI + SQLite，
负责提供 HTTP 接口、页面托管、数据库读写与小票打印。

## 目录内容

| 路径 | 说明 |
| --- | --- |
| `app/` | 应用源码（接口、模型、配置、打印服务、启动器） |
| `tests/` | 自动化测试（pytest） |
| `requirements.txt` | Python 依赖版本清单 |
| `pytest.ini` | pytest 配置 |
| `run.py` | 源码模式启动入口（等价于 `python -m app`） |
| `.venv/` | 虚拟环境（不纳入版本管理） |

## 运行时生成的文件

源码模式下，运行时数据位于**项目根目录**（`backend` 的上一级），由程序自动创建：

| 路径 | 说明 |
| --- | --- |
| `../data/` | SQLite 数据库（`restaurant.db`） |
| `../logs/` | 日志文件（`app.log`，按天滚动保留 14 天） |
| `../printed/` | 模拟打印的小票文本 |
| `../config.json` | 本地配置 |

## 常用命令

```bash
./.venv/bin/python -m app          # 启动服务
./.venv/bin/python -m pytest -q    # 运行测试
```
