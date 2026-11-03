# frontend/stats —— 营业统计页

## 功能说明 / Overview

小店营业额统计页面，只读展示指定区间的经营数据。
Read-only revenue statistics page for the shop.

- 路由：`/stats`（由 `backend/app/main.py` 的 `stats_page` 提供）
- 数据来源：`GET /api/stats/revenue?range=today|7d|30d|custom[&start=&end=]`
- 依赖脚本：`/static/vendor/vue.global.prod.js`、`/static/js/api.js`、`/static/js/common.js`
- 样式：`/static/css/base.css` + 页面内联样式

## 页面内容 / Page sections

| 区块 | 说明 |
| --- | --- |
| 区间切换 | 今日 / 近 7 天 / 近 30 天 / 自定义（自定义展开两个日期输入框） |
| 指标卡 | 营业额、已结账单数、客单价 |
| 每日营业额 | 手写内联 SVG 折线图，无外部图表库 |
| 菜品销量排行 | 最多 10 条，按金额降序 |

## 约定 / Conventions

- 不引用任何外部 CDN，断网可用。
- 不订阅 SSE：切换区间或重新进入页面即刷新。
- 金额统一由后端返回两位小数字符串，前端仅做展示格式化。
- 客单价为空（区间内无已结账订单）时显示 `—`。
