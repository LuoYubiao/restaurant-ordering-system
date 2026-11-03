"""ESC/POS 打印服务模块。

ESC/POS printing service module.

提供两类能力：
1. 纯文本小票渲染（可单元测试，不依赖真实打印机）；
2. 实际打印执行（模拟 / 网口 / USB），失败时绝不向调用方抛异常。

Provides two capabilities:
1. Plain-text ticket rendering (unit-testable, no real printer needed);
2. Actual printing (mock / network / USB). Failures never raise to callers.

关于中文编码：python-escpos 3.1 在默认 ``AUTO`` 字符集下会自动把中日韩字符
编码为 GB18030，因此无需手动调用 ``charcode("CP936")``（该编码名不在内置
码表中，强行调用会报错）。
About Chinese encoding: python-escpos 3.1 automatically encodes CJK characters
as GB18030 under the default ``AUTO`` charcode, so there is no need to call
``charcode("CP936")`` (that name is not in the built-in codepage table).
"""

from __future__ import annotations

import logging
import socket
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import PrinterConfig, get_config
from ..money import fen_to_yuan, yuan_to_fen
from ..paths import get_printed_dir

logger = logging.getLogger(__name__)

# 最大重试次数（不含首次尝试）/ Max retries (excluding the first attempt)
MAX_RETRIES = 2
# 重试间隔（秒）/ Retry interval in seconds
RETRY_INTERVAL = 0.5
# 网口连接超时（秒）/ Network connect timeout in seconds
NETWORK_TIMEOUT = 10
# 单行分隔线字符 / Separator character for a full line
SEPARATOR_CHAR = "-"
# 厨房单需要放大加粗的行号（0 起）：第 0 行为店名，第 1 行为桌号
# Line index (0-based) emphasized on the kitchen ticket: index 1 is the table number
KITCHEN_EMPHASIS_LINE_INDEX = 1

# 缓存的打印机连接及标识 / Cached printer connection and its identity key
_cached_printer: Optional[Any] = None
_cached_key: Optional[tuple] = None


@dataclass
class PrintResult:
    """打印结果数据类。

    Print result dataclass.
    """

    # 打印目标：counter / kitchen / Print target: counter / kitchen
    target: str
    # 是否成功 / Whether succeeded
    ok: bool
    # 结果说明 / Result message
    message: str


def chars_per_line(paper_width: int) -> int:
    """根据纸张宽度返回每行可容纳的字符数。

    Return the number of characters per line for the given paper width.

    :param paper_width: 纸张宽度毫米（58 / 80）/ paper width in mm (58 / 80)
    :return: 每行字符数（58 -> 32，80 -> 48）/ chars per line (58 -> 32, 80 -> 48)
    """
    return 48 if paper_width and paper_width >= 80 else 32


def display_width(text: str) -> int:
    """计算字符串的显示宽度（中文等全角字符按 2 计）。

    Compute the display width of a string (wide/fullwidth chars count as 2).

    :param text: 待计算文本 / input text
    :return: 显示宽度 / display width
    """
    width = 0
    for char in text:
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def pad_right(text: str, width: int) -> str:
    """在右侧补空格到指定显示宽度。

    Pad the string with spaces on the right up to the given display width.

    :param text: 原文本 / source text
    :param width: 目标显示宽度 / target display width
    :return: 补位后的文本 / padded text
    """
    padding = width - display_width(text)
    return text + (" " * padding if padding > 0 else "")


def pad_left(text: str, width: int) -> str:
    """在左侧补空格到指定显示宽度。

    Pad the string with spaces on the left up to the given display width.

    :param text: 原文本 / source text
    :param width: 目标显示宽度 / target display width
    :return: 补位后的文本 / padded text
    """
    padding = width - display_width(text)
    return (" " * padding if padding > 0 else "") + text


def center(text: str, width: int) -> str:
    """把文本按显示宽度居中。

    Center the text within the given display width.

    :param text: 原文本 / source text
    :param width: 目标显示宽度 / target display width
    :return: 居中后的文本 / centered text
    """
    padding = width - display_width(text)
    if padding <= 0:
        return text
    left = padding // 2
    right = padding - left
    return (" " * left) + text + (" " * right)


def _separator(width: int) -> str:
    """生成一行分隔线。

    Build a single separator line.

    :param width: 行宽 / line width
    :return: 分隔线字符串 / separator string
    """
    return SEPARATOR_CHAR * width


def _wrap_by_width(text: str, width: int) -> List[str]:
    """按显示宽度把文本拆分为多行。

    Split text into multiple lines by display width.

    :param text: 原文本 / source text
    :param width: 每行最大显示宽度 / max display width per line
    :return: 文本行列表 / list of lines
    """
    lines: List[str] = []
    current = ""
    current_width = 0
    for char in text:
        char_width = 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
        if current_width + char_width > width and current:
            lines.append(current)
            current = ""
            current_width = 0
        current += char
        current_width += char_width
    lines.append(current)
    return lines


def _two_column_lines(left: str, right: str, width: int) -> List[str]:
    """生成「左对齐 + 右对齐」两列布局的行。

    Build lines for a two-column layout (left aligned + right aligned). When
    the content is too wide, the left part wraps and the right part is placed
    on the last line.

    :param left: 左侧文本 / left text
    :param right: 右侧文本 / right text
    :param width: 行宽 / line width
    :return: 行列表 / list of lines
    """
    right_width = display_width(right)
    if display_width(left) + right_width < width:
        return [left + (" " * (width - display_width(left) - right_width)) + right]

    available = max(width - right_width - 1, 1)
    chunks = _wrap_by_width(left, available)
    lines = [chunk for chunk in chunks[:-1]]
    last = chunks[-1]
    gap = width - display_width(last) - right_width
    lines.append(last + (" " * gap if gap > 0 else " ") + right)
    return lines


def _format_time(value: Any) -> str:
    """把时间值格式化为 ``YYYY-MM-DD HH:mm``。

    Format a time value as ``YYYY-MM-DD HH:mm``.

    :param value: ISO 字符串或 datetime / ISO string or datetime
    :return: 格式化时间字符串 / formatted time string
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    text = str(value)
    try:
        return datetime.fromisoformat(text).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return text


def _item_table_lines(
    name: str,
    quantity: str,
    unit_price: str,
    subtotal: str,
    width: int,
) -> List[str]:
    """把菜品明细渲染为四列文本，名称列左对齐、其余三列右对齐。

    Render an order item as a four-column text table row: the name column is
    left aligned while quantity, unit price and subtotal are right aligned, so
    that both the header and every item row share the same column right edges.

    :param name: 菜品名称 / dish name
    :param quantity: 数量文本 / quantity text
    :param unit_price: 单价文本 / unit price text
    :param subtotal: 小计文本 / subtotal text
    :param width: 总行宽 / total line width
    :return: 行列表 / rendered lines
    """
    quantity_width = 4
    unit_price_width = 6
    subtotal_width = 6
    gap_width = 3
    name_width = max(width - quantity_width - unit_price_width - subtotal_width - gap_width, 1)
    name_lines = _wrap_by_width(name, name_width)
    rows: List[str] = []

    for index, line in enumerate(name_lines):
        qty_cell = quantity if index == 0 else ""
        unit_cell = unit_price if index == 0 else ""
        subtotal_cell = subtotal if index == 0 else ""
        rows.append(
            pad_right(line, name_width)
            + " "
            + pad_left(qty_cell, quantity_width)
            + " "
            + pad_left(unit_cell, unit_price_width)
            + " "
            + pad_left(subtotal_cell, subtotal_width)
        )
    return rows


def _item_subtotal_fen(item: Dict[str, Any]) -> int:
    """计算单条明细的小计（分）。

    Compute the subtotal (in fen) of a single order item.

    :param item: 明细字典 / item dict
    :return: 小计（分）/ subtotal in fen
    """
    try:
        unit_fen = yuan_to_fen(item.get("price", 0))
    except ValueError:
        unit_fen = 0
    return unit_fen * int(item.get("quantity", 0) or 0)


def render_counter_ticket(order_view: Dict[str, Any], shop_name: str, paper_width: int) -> str:
    """渲染柜台小票（含价格）。

    Render the counter ticket (with prices).

    :param order_view: 订单视图字典（键同 OrderOut）/ order view dict (keys as OrderOut)
    :param shop_name: 店铺名称 / shop name
    :param paper_width: 纸张宽度毫米 / paper width in mm
    :return: 小票纯文本 / plain-text ticket
    """
    width = chars_per_line(paper_width)
    lines: List[str] = []

    # 店名（居中，加粗）/ Shop name (centered, bold)
    lines.append(center(shop_name, width))
    lines.append(_separator(width))

    # 订单基础信息 / Basic order info
    lines.append(f"订单号: {order_view.get('orderNo', '')}")
    table_no = order_view.get("tableNo")
    table_text = table_no if table_no else "打包"
    lines.append(f"桌号: {table_text}")
    lines.append(f"时间: {_format_time(order_view.get('createdTime'))}")
    lines.append(_separator(width))

    # 菜品明细 / Dish items
    lines.extend(_item_table_lines("菜品名称", "数量", "单价", "小计", width))
    lines.append(_separator(width))
    for item in order_view.get("items", []) or []:
        name = str(item.get("dishName", ""))
        quantity = int(item.get("quantity", 0) or 0)
        subtotal_fen = _item_subtotal_fen(item)
        lines.extend(
            _item_table_lines(
                name,
                str(quantity),
                str(item.get("price", "0.00")),
                fen_to_yuan(subtotal_fen),
                width,
            )
        )
        remark = item.get("remark")
        if remark:
            for remark_line in _wrap_by_width(f"  备注: {remark}", width):
                lines.append(remark_line)

    lines.append(_separator(width))

    # 合计（加粗）/ Total (bold)
    total_text = order_view.get("totalAmount", "0.00")
    lines.extend(_two_column_lines("合计", str(total_text), width))

    # 订单备注 / Order remark
    order_remark = order_view.get("remark")
    if order_remark:
        for remark_line in _wrap_by_width(f"备注: {order_remark}", width):
            lines.append(remark_line)

    lines.append(_separator(width))
    # 页脚 / Footer
    lines.append(center("谢谢惠顾", width))
    lines.append("")
    return "\n".join(lines)


def render_kitchen_ticket(order_view: Dict[str, Any], shop_name: str, paper_width: int) -> str:
    """渲染厨房小票（不含价格，突出桌号与数量）。

    Render the kitchen ticket (no prices; highlights table number and quantity).

    :param order_view: 订单视图字典（键同 OrderOut）/ order view dict (keys as OrderOut)
    :param shop_name: 店铺名称 / shop name
    :param paper_width: 纸张宽度毫米 / paper width in mm
    :return: 小票纯文本 / plain-text ticket
    """
    width = chars_per_line(paper_width)
    lines: List[str] = []

    # 店名（小字）/ Shop name (small)
    lines.append(shop_name)

    # 桌号（大字）/ Table number (large)
    table_no = order_view.get("tableNo")
    lines.append(table_no if table_no else "打包")
    lines.append(f"时间: {_format_time(order_view.get('createdTime'))}")
    lines.append(_separator(width))

    # 菜品与数量（不含价格，数量加大）/ Dishes and quantities (no prices, larger quantity)
    for item in order_view.get("items", []) or []:
        name = str(item.get("dishName", ""))
        quantity = int(item.get("quantity", 0) or 0)
        lines.append(f"{name}  x {quantity}")
        remark = item.get("remark")
        if remark:
            for remark_line in _wrap_by_width(f"  备注: {remark}", width):
                lines.append(remark_line)

    lines.append(_separator(width))
    lines.append("")
    return "\n".join(lines)


def _mock_write(target: str, text: str) -> Path:
    """把模拟打印内容写入文件。

    Write the mock print output to a file.

    :param target: 打印目标 / print target
    :param text: 小票文本 / ticket text
    :return: 写入的文件路径 / written file path
    """
    printed_dir = get_printed_dir()
    printed_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = printed_dir / f"{stamp}_{target}.txt"
    index = 1
    while path.exists():
        path = printed_dir / f"{stamp}_{target}_{index}.txt"
        index += 1
    path.write_text(text, encoding="utf-8")
    return path


def _build_printer(printer_cfg: PrinterConfig) -> Any:
    """根据配置创建打印机对象。

    Create a printer object from the given configuration.

    :param printer_cfg: 打印机配置 / printer config
    :return: escpos 打印机实例 / escpos printer instance
    """
    from escpos.printer import Network, Usb

    mode = (printer_cfg.mode or "mock").lower()
    if mode == "network":
        return Network(host=printer_cfg.host, port=printer_cfg.port, timeout=NETWORK_TIMEOUT)
    if mode == "usb":
        return Usb(
            idVendor=printer_cfg.usbVendorId,
            idProduct=printer_cfg.usbProductId,
            timeout=NETWORK_TIMEOUT,
        )
    raise ValueError(f"unsupported printer mode: {printer_cfg.mode}")


def _printer_identity(printer_cfg: PrinterConfig) -> tuple:
    """返回打印机连接的标识元组（用于缓存判断）。

    Return an identity tuple for the printer connection (used for caching).

    :param printer_cfg: 打印机配置 / printer config
    :return: 标识元组 / identity tuple
    """
    return (
        (printer_cfg.mode or "mock").lower(),
        printer_cfg.host,
        printer_cfg.port,
        printer_cfg.usbVendorId,
        printer_cfg.usbProductId,
    )


def _get_printer(printer_cfg: PrinterConfig) -> Any:
    """获取（必要时创建并缓存）打印机连接对象。

    Get a printer object, creating and caching it when necessary.

    :param printer_cfg: 打印机配置 / printer config
    :return: escpos 打印机实例 / escpos printer instance
    """
    global _cached_printer, _cached_key
    key = _printer_identity(printer_cfg)
    if _cached_printer is not None and _cached_key == key:
        return _cached_printer
    reload_printer()
    _cached_printer = _build_printer(printer_cfg)
    _cached_key = key
    return _cached_printer


def reload_printer() -> None:
    """清空缓存的打印机连接（配置热更新后调用）。

    Clear the cached printer connection (call after config hot-reload).
    """
    global _cached_printer, _cached_key
    if _cached_printer is not None:
        try:
            _cached_printer.close()
        except Exception:  # noqa: BLE001 - closing must never raise here
            logger.debug("Ignoring error while closing cached printer")
    _cached_printer = None
    _cached_key = None


def _describe_error(exc: Exception, printer_cfg: PrinterConfig) -> str:
    """把异常转换为可读的中文失败原因。

    Convert an exception into a readable failure reason.

    :param exc: 捕获到的异常 / caught exception
    :param printer_cfg: 打印机配置 / printer config
    :return: 中文失败原因 / readable failure reason
    """
    mode = (printer_cfg.mode or "mock").lower()
    if mode == "usb" and (printer_cfg.usbVendorId is None or printer_cfg.usbProductId is None):
        return "打印机未配置（缺少 USB 厂商/产品 ID）"
    if isinstance(exc, socket.timeout):
        return "连接超时，请检查打印机是否在线"
    if isinstance(exc, ConnectionRefusedError):
        return "连接被拒绝，请检查打印机 IP 与端口"
    if isinstance(exc, (socket.gaierror, OSError)):
        return f"网络连接失败：{exc}"
    return f"打印失败：{exc}"


def _do_print(printer_cfg: PrinterConfig, text: str, target: str = "ticket") -> None:
    """实际发送文本到打印机。

    Actually send the text to the printer. The default ``AUTO`` charcode
    handles Chinese (GB18030) automatically. Kitchen tickets print the table
    number line bold and double-sized so it is readable from a distance.

    :param printer_cfg: 打印机配置 / printer config
    :param text: 小票文本 / ticket text
    :param target: 打印目标 / print target
    """
    printer = _get_printer(printer_cfg)
    emphasize = target == "kitchen"
    for index, line in enumerate(text.split("\n")):
        if emphasize and index == KITCHEN_EMPHASIS_LINE_INDEX and line.strip():
            # 桌号加粗放大 / Table number in bold and doubled size
            printer.set(bold=True, double_width=True, double_height=True)
            printer.textln(line)
            printer.set(bold=False, double_width=False, double_height=False)
            continue
        printer.textln(line)
    printer.cut()
    logger.info("Ticket sent to printer, mode=%s target=%s", printer_cfg.mode, target)


def _send_text(text: str, target: str = "ticket") -> PrintResult:
    """把渲染好的文本发送到打印机（含重试，绝不抛异常）。

    Send the rendered text to the printer (with retries; never raises).

    :param text: 小票文本 / ticket text
    :param target: 打印目标 / print target
    :return: 打印结果 / print result
    """
    printer_cfg = get_config().printer
    mode = (printer_cfg.mode or "mock").lower()

    # 模拟模式：写入文本文件 / Mock mode: write to a text file
    if mode == "mock":
        path = _mock_write(target, text)
        logger.info("Mock print saved, target=%s path=%s", target, path)
        return PrintResult(
            target=target,
            ok=True,
            message=f"模拟打印，未连接真实打印机（已保存到 {path}）",
        )

    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            _do_print(printer_cfg, text, target)
            return PrintResult(target=target, ok=True, message="打印成功")
        except Exception as exc:  # noqa: BLE001 - printing must never raise
            last_error = exc
            logger.warning(
                "Print attempt failed, target=%s mode=%s attempt=%s error=%s",
                target,
                mode,
                attempt,
                exc,
            )
            reload_printer()
            if attempt <= MAX_RETRIES:
                time.sleep(RETRY_INTERVAL)

    reason = _describe_error(last_error, printer_cfg) if last_error else "打印失败"
    logger.error("Print failed after retries, target=%s reason=%s", target, reason)
    return PrintResult(target=target, ok=False, message=reason)


def print_order(
    order_view: Dict[str, Any], targets: Optional[List[str]] = None
) -> List[PrintResult]:
    """打印订单小票。

    Print the order tickets. When ``targets`` is not given, it is derived from
    the configured print switches.

    :param order_view: 订单视图字典（键同 OrderOut）/ order view dict (keys as OrderOut)
    :param targets: 打印目标列表（counter / kitchen），默认按配置决定
        / target list (counter / kitchen), defaults to the configured switches
    :return: 打印结果列表 / list of print results
    """
    cfg = get_config()
    if targets is None:
        resolved: List[str] = []
        if cfg.printCounterTicket:
            resolved.append("counter")
        if cfg.printKitchenTicket:
            resolved.append("kitchen")
        targets = resolved

    results: List[PrintResult] = []
    paper_width = cfg.printer.paperWidth
    for target in targets:
        if target == "counter":
            text = render_counter_ticket(order_view, cfg.shopName, paper_width)
        elif target == "kitchen":
            text = render_kitchen_ticket(order_view, cfg.shopName, paper_width)
        else:
            results.append(
                PrintResult(target=target, ok=False, message=f"未知打印目标：{target}")
            )
            continue
        results.append(_send_text(text, target))
    return results


def test_print() -> PrintResult:
    """打印一张测试小票。

    Print a test ticket showing the shop name, current time and a health
    message.

    :return: 打印结果 / print result
    """
    cfg = get_config()
    width = chars_per_line(cfg.printer.paperWidth)
    lines = [
        center(cfg.shopName, width),
        _separator(width),
        center("打印机连接正常", width),
        center(_format_time(datetime.now()), width),
        _separator(width),
        "",
    ]
    return _send_text("\n".join(lines), "test")
