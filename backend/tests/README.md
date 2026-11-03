# tests 测试目录说明

后端自动化测试目录（pytest）。

| 文件 | 说明 |
| --- | --- |
| `conftest.py` | 公共夹具：隔离数据目录、重置缓存/引擎、TestClient、数据库会话 |
| `test_smoke.py` | 冒烟测试：健康检查、首页重定向、运行时文件生成、种子数据幂等 |
| `__init__.py` | 测试包标识 |

## 运行方式

```bash
cd backend
./.venv/bin/python -m pytest -q
```

## 测试隔离

夹具通过设置环境变量 `ROS_DATA_DIR` 指向临时目录，并在每个测试前后重置
配置缓存（`config.reset_config_cache`）与数据库引擎（`database.reset_engine`），
确保每个测试使用全新数据库，互不干扰。
