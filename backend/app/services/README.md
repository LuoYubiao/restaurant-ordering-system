# services 业务服务目录说明

存放与具体 HTTP 接口解耦的业务服务。

| 文件 | 说明 |
| --- | --- |
| `printer_service.py` | ESC/POS 小票打印服务：纯文本渲染 + 实际打印（模拟/网口/USB） |
| `__init__.py` | 统一导出 |

## printer_service 关键能力

- `render_counter_ticket(order_view, shop_name, paper_width)`：渲染柜台小票（含价格）。
- `render_kitchen_ticket(order_view, shop_name, paper_width)`：渲染厨房小票（不含价格）。
- `print_order(order_view, targets=None)`：按配置打印柜台单/厨房单，返回 `PrintResult` 列表。
- `test_print()`：打印一张测试小票。
- `reload_printer()`：配置热更新后清空缓存的打印机连接。
- `display_width` / `pad_right` / `center`：中文宽度对齐工具（全角按 2 计算）。

## 约定

- 打印失败**绝不向调用方抛异常**，统一以 `PrintResult(ok=False, message=...)` 返回可读原因。
- 模拟模式（`mode=mock`）会把小票文本写入 `printed/` 目录，便于无打印机验证排版。
- 中文编码：python-escpos 3.1 在默认 `AUTO` 字符集下会自动以 GB18030 编码中文，无需手动指定码表。
