# kitchen 厨房看板页

对应访问地址 `/kitchen`，供后厨大屏实时查看与处理订单。

- 页面文件：`index.html`（由后续页面任务实现）。
- 依赖共享资源：`/static/css/base.css`、`/static/js/api.js`、`/static/js/sse.js`、`/static/js/common.js`。
- 主要功能规划：实时接收新订单（SSE）、按菜品/桌号展示待出餐项、标记出餐完成、新单提示音（`ROS.beep`）。
