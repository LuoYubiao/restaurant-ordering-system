# vendor 第三方库目录 / Third-party libraries

本目录存放离线可用的第三方前端库，**禁止改回 CDN 引用**，以保证断网/内网环境下系统仍可正常使用。
This directory stores offline third-party frontend libraries. **Do not switch back to CDN references** so the system keeps working without internet or on an intranet.

## 文件清单 / Files

- `vue.global.prod.js`
  - 来源 / Source: unpkg `vue@3.4.38`，文件 `dist/vue.global.prod.js`
  - 用途 / Purpose: Vue 3 生产版全局构建，供柜台/厨房/管理/设置页面离线使用
  - 说明 / Note: 该文件为官方发行文件，请勿修改其内容
