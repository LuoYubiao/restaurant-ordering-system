# static/js 脚本目录说明

页面共用的脚本目录，全部挂在全局 `window.ROS` 命名空间下，本地文件，**禁止引用外部 CDN**。

| 文件 | 说明 |
| --- | --- |
| `api.js` | `window.ROS` 请求封装：`get/post/put/patch/del`，统一错误处理 |
| `sse.js` | `ROS.connectStream({ onEvent, onReconnect })`：实时事件流（SSE） |
| `common.js` | 通用工具：金额 / 时间格式化、状态文案、徽标样式、`toast` 提示、`beep` 提示音 |

引入顺序（须在 Vue 之后）：

```html
<script src="/static/js/api.js"></script>
<script src="/static/js/sse.js"></script>
<script src="/static/js/common.js"></script>
```
