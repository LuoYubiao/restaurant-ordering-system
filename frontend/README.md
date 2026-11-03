# frontend 前端目录说明

系统的前端页面与静态资源目录。所有页面为**纯静态 HTML + Vue 3（离线全局构建）**，
由后端直接托管，无需 Node/构建工具。

| 目录 / 文件 | 说明 |
| --- | --- |
| `counter/` | 柜台点菜页（`/counter`） |
| `kitchen/` | 厨房看板页（`/kitchen`） |
| `admin/` | 菜品管理页（`/admin`） |
| `settings/` | 系统设置页（`/settings`） |
| `static/` | 共享静态资源（CSS / JS / 第三方库） |

## 页面访问地址

| 页面 | 本机地址 | 局域网地址 |
| --- | --- | --- |
| 柜台点菜 | `http://127.0.0.1:<端口>/counter` | `http://<本机IP>:<端口>/counter` |
| 厨房看板 | `http://127.0.0.1:<端口>/kitchen` | `http://<本机IP>:<端口>/kitchen` |
| 菜品管理 | `http://127.0.0.1:<端口>/admin` | `http://<本机IP>:<端口>/admin` |
| 系统设置 | `http://127.0.0.1:<端口>/settings` | `http://<本机IP>:<端口>/settings` |

## 约定

- 页面直接引用 `static/` 下的本地资源，**禁止使用 CDN**，保证内网/断网可用。
- 通用能力（请求、实时事件流、金额/时间格式化、提示音等）统一由 `static/js/` 提供。
