# static 共享静态资源目录说明

页面共用的样式、脚本与第三方库，全部为本地文件，**禁止改回 CDN 引用**。

| 目录 / 文件 | 说明 |
| --- | --- |
| `css/base.css` | 基础设计系统：CSS 变量、重置、按钮/卡片/徽标/表格/弹窗/提示等组件、布局工具类 |
| `js/api.js` | `window.ROS` 请求封装：`get/post/put/patch/del`，统一错误处理 |
| `js/sse.js` | `ROS.connectStream({ onEvent, onReconnect })`：实时事件流（SSE） |
| `js/common.js` | 通用工具：金额/时间格式化、状态文案、徽标样式、`toast` 提示、`beep` 提示音 |
| `vendor/` | 离线第三方库（Vue 3），详见 `vendor/README.md` |

## 使用顺序

页面应按以下顺序引入脚本：

```html
<link rel="stylesheet" href="/static/css/base.css" />
<script src="/static/vendor/vue.global.prod.js"></script>
<script src="/static/js/api.js"></script>
<script src="/static/js/sse.js"></script>
<script src="/static/js/common.js"></script>
```
