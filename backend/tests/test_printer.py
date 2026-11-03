"""ESC/POS 打印服务测试。

Tests for the ESC/POS printing service.

覆盖：小票文本渲染（柜台单含价格、厨房单不含价格）、纸张宽度排版、
模拟打印落盘，以及厨房单桌号行的加粗放大指令。
Covers: ticket rendering (counter ticket with prices, kitchen ticket without),
paper-width layout, mock printing to disk, and the bold/double-size instruction
applied to the kitchen ticket's table-number line.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import pytest

from app.services import printer_service
from app.services.printer_service import (
    chars_per_line,
    display_width,
    render_counter_ticket,
    render_kitchen_ticket,
)


def _order_view() -> Dict[str, Any]:
    """构造一个用于渲染的订单视图字典。

    Build an order view dict used for ticket rendering.

    :return: 订单视图字典 / order view dict
    """
    return {
        "orderNo": "20260101-0001",
        "tableNo": "A8",
        "diningType": "dine_in",
        "status": "pending",
        "totalAmount": "84.00",
        "remark": "少辣",
        "createdTime": "2026-01-01T12:30:00",
        "items": [
            {"dishName": "宫保鸡丁", "price": "28.00", "quantity": 2, "remark": "不要葱"},
            {"dishName": "米饭", "price": "2.00", "quantity": 3, "remark": None},
        ],
    }


def _right_edge(line: str, token: str) -> int:
    """返回 token 在行内的右边界显示宽度。

    Return the right boundary (in display width) of ``token`` inside ``line``.

    :param line: 整行文本 / the whole line
    :param token: 目标片段 / the target token
    :return: 右边界显示宽度 / right boundary in display width
    """
    start = line.index(token)
    return display_width(line[:start]) + display_width(token)


# ---------------------------------------------------------------------------
# 排版基础 / Layout primitives
# ---------------------------------------------------------------------------


def test_chars_per_line_by_paper_width() -> None:
    """58mm 纸每行 32 字符，80mm 纸每行 48 字符。

    58mm paper fits 32 chars per line; 80mm paper fits 48.
    """
    assert chars_per_line(58) == 32
    assert chars_per_line(80) == 48
    # 小于 58 或未配置时回退到 58mm 的排版 / Anything below 58 falls back to 58mm
    assert chars_per_line(0) == 32
    assert chars_per_line(58) == 32


def test_display_width_counts_cjk_as_two() -> None:
    """中文按 2 个宽度计算，ASCII 按 1 个宽度计算。

    CJK characters count as width 2, ASCII as width 1.
    """
    assert display_width("abc") == 3
    assert display_width("宫保") == 4
    assert display_width("宫保鸡丁 x 2") == 12


@pytest.mark.parametrize("paper_width", [58, 80])
def test_ticket_lines_fit_paper_width(paper_width: int) -> None:
    """两种纸张宽度下，渲染出的每一行都不得超过每行字符数。

    For both paper widths, no rendered line may exceed the per-line capacity.
    """
    width = chars_per_line(paper_width)
    order_view = _order_view()
    for text in (
        render_counter_ticket(order_view, "我的小店", paper_width),
        render_kitchen_ticket(order_view, "我的小店", paper_width),
    ):
        for line in text.split("\n"):
            assert display_width(line) <= width, f"overflow line={line!r} width={paper_width}"


# ---------------------------------------------------------------------------
# 柜台小票 / Counter ticket
# ---------------------------------------------------------------------------


def test_counter_ticket_contains_key_fields() -> None:
    """柜台小票应包含店名、订单号、桌号、时间、菜品（含单价与小计）、合计与备注。

    The counter ticket must contain the shop name, order number, table number,
    time, dishes (unit price and subtotal), total and remarks.
    """
    text = render_counter_ticket(_order_view(), "我的小店", 58)

    assert "我的小店" in text
    assert "20260101-0001" in text
    assert "A8" in text
    assert "2026-01-01 12:30" in text
    assert "宫保鸡丁" in text
    assert "2" in text
    assert "28.00" in text
    assert "56.00" in text  # 小计 = 28.00 x 2 / subtotal
    assert "米饭" in text
    assert "3" in text
    assert "合计" in text
    assert "84.00" in text  # 由 totalAmount 提供 / provided by totalAmount
    assert "不要葱" in text
    assert "少辣" in text
    assert "谢谢惠顾" in text


def test_counter_ticket_contains_item_header() -> None:
    """柜台小票应包含四列表头，名称列左对齐、数量/单价/小计三列右对齐。

    The counter ticket must include a four-column item header; the name column is
    left aligned while quantity, unit price and subtotal are right aligned.
    """
    text = render_counter_ticket(_order_view(), "我的小店", 58)
    lines = text.split("\n")
    header = next(
        line for line in lines if "菜品名称" in line and "数量" in line and "单价" in line and "小计" in line
    )
    first_item = next(line for line in lines if "宫保鸡丁" in line and "28.00" in line and "56.00" in line)
    second_item = next(line for line in lines if "米饭" in line and "2.00" in line and "6.00" in line)

    assert "菜品名称" in header
    assert "数量" in header
    assert "单价" in header
    assert "小计" in header
    assert "份数" not in header

    # 名称列左对齐 / The name column is left aligned
    assert header.startswith("菜品名称")
    assert first_item.startswith("宫保鸡丁")
    assert second_item.startswith("米饭")

    # 三列数值右对齐：表头与明细行的右边界必须一致
    # The three numeric columns are right aligned: the right edges of the header
    # and of every item row must coincide.
    quantity_edge = _right_edge(header, "数量")
    assert _right_edge(first_item, "2") == quantity_edge
    assert _right_edge(second_item, "3") == quantity_edge

    unit_price_edge = _right_edge(header, "单价")
    assert _right_edge(first_item, "28.00") == unit_price_edge
    assert _right_edge(second_item, "2.00") == unit_price_edge

    subtotal_edge = _right_edge(header, "小计")
    assert _right_edge(first_item, "56.00") == subtotal_edge
    assert _right_edge(second_item, "6.00") == subtotal_edge


def test_counter_ticket_centers_shop_name() -> None:
    """店名应居中显示。

    The shop name should be centered.
    """
    text = render_counter_ticket(_order_view(), "我的小店", 58)
    first_line = text.split("\n")[0]
    padding = " " * ((32 - 8) // 2)
    assert first_line == padding + "我的小店" + padding


# ---------------------------------------------------------------------------
# 厨房小票 / Kitchen ticket
# ---------------------------------------------------------------------------


def test_kitchen_ticket_has_no_price() -> None:
    """厨房制作单只含桌号、菜名与数量、口味备注，不得出现任何价格。

    The kitchen ticket must contain the table number, dish names, quantities
    and remarks, and must not contain any price.
    """
    text = render_kitchen_ticket(_order_view(), "我的小店", 58)

    assert "A8" in text
    assert "宫保鸡丁  x 2" in text
    assert "米饭  x 3" in text
    assert "不要葱" in text
    assert "少辣" not in text  # 订单备注属柜台单 / order remark belongs to the counter ticket

    # 不含任何价格信息 / No price information at all
    for money in ("28.00", "2.00", "56.00", "6.00", "84.00", "合计", "小计"):
        assert money not in text, f"unexpected price token {money!r}"


# ---------------------------------------------------------------------------
# 模拟打印落盘 / Mock printing to disk
# ---------------------------------------------------------------------------


def test_mock_print_writes_counter_and_kitchen_files(data_dir: str) -> None:
    """模拟模式下打印订单应在 printed/ 生成柜台单与厨房单文本。

    In mock mode printing an order writes the counter and kitchen ticket text
    files into ``printed/``.
    """
    results = printer_service.print_order(_order_view(), targets=["counter", "kitchen"])

    assert [r.target for r in results] == ["counter", "kitchen"]
    assert all(r.ok for r in results)

    printed_dir = os.path.join(data_dir, "printed")
    files = sorted(os.listdir(printed_dir))
    assert any(name.endswith("_counter.txt") for name in files), files
    assert any(name.endswith("_kitchen.txt") for name in files), files

    counter_file = next(n for n in files if n.endswith("_counter.txt"))
    kitchen_file = next(n for n in files if n.endswith("_kitchen.txt"))
    with open(os.path.join(printed_dir, counter_file), "r", encoding="utf-8") as fp:
        assert "20260101-0001" in fp.read()
    with open(os.path.join(printed_dir, kitchen_file), "r", encoding="utf-8") as fp:
        assert "28.00" not in fp.read()


def test_mock_print_uses_configured_switches(data_dir: str) -> None:
    """未显式指定目标时，按 config 中的打印开关决定打印哪几张单。

    When targets are not given explicitly, the configured print switches decide
    which tickets are printed.
    """
    printer_service.print_order(_order_view(), targets=None)

    files = os.listdir(os.path.join(data_dir, "printed"))
    assert any(name.endswith("_counter.txt") for name in files), files
    assert any(name.endswith("_kitchen.txt") for name in files), files


def test_reload_printer_is_safe_without_connection() -> None:
    """未建立连接时清空打印缓存不应抛异常。

    Clearing the printer cache without an established connection must not raise.
    """
    printer_service.reload_printer()
    printer_service.reload_printer()


def test_test_print_mock_succeeds(data_dir: str) -> None:
    """模拟模式下测试打印应返回成功并落盘。

    The test print should succeed and write a file in mock mode.
    """
    result = printer_service.test_print()
    assert result.ok is True
    assert result.target == "test"
    assert "模拟打印" in result.message


# ---------------------------------------------------------------------------
# 厨房单加粗放大指令 / Kitchen emphasis instructions
# ---------------------------------------------------------------------------


class _RecordingPrinter:
    """记录调用序列的假打印机，用于断言发送了哪些 ESC/POS 指令。

    A fake printer recording the call sequence, used to assert which ESC/POS
    instructions were sent.
    """

    def __init__(self) -> None:
        # 事件序列：("set", kwargs) / ("text", line) / ("cut", None)
        # Event sequence: ("set", kwargs) / ("text", line) / ("cut", None)
        self.events: List[Tuple[str, Any]] = []

    def set(self, **kwargs: Any) -> None:
        """记录一次样式设置指令。

        Record a style-setting instruction.
        """
        self.events.append(("set", kwargs))

    def textln(self, text: str) -> None:
        """记录一行文本输出。

        Record a single text line.
        """
        self.events.append(("text", text))

    def cut(self) -> None:
        """记录一次切纸指令。

        Record a cut instruction.
        """
        self.events.append(("cut", None))


def _install_recording_printer(monkeypatch: pytest.MonkeyPatch) -> _RecordingPrinter:
    """把伪打印机注入打印服务并返回该对象。

    Inject the fake printer into the printing service and return it.

    :param monkeypatch: pytest monkeypatch 夹具 / pytest monkeypatch fixture
    :return: 伪打印机 / fake printer
    """
    recorder = _RecordingPrinter()
    monkeypatch.setattr(printer_service, "_get_printer", lambda _cfg: recorder)
    return recorder


def test_kitchen_ticket_emphasizes_table_number_line(
    data_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """厨房单第 2 行（桌号）应加粗放大，其余行不改变样式。

    On the kitchen ticket, line index 1 (the table number) must be bold and
    double-sized, while other lines keep the default style.
    """
    # 切换到网口模式，跳过 mock 分支以走真实发送路径
    # Switch to network mode so the real send path (not the mock branch) runs.
    printer_service.get_config().printer.mode = "network"
    recorder = _install_recording_printer(monkeypatch)

    text = render_kitchen_ticket(_order_view(), "我的小店", 58)
    printer_service._do_print(printer_service.get_config().printer, text, "kitchen")

    text_events = [(i, value) for i, (kind, value) in enumerate(recorder.events) if kind == "text"]
    assert text_events[0][1] == "我的小店"  # 第 0 行店名不加粗 / line 0 is not emphasized
    table_index, table_line = text_events[1]
    assert table_line == "A8"

    # 桌号前必然紧跟一条加粗放大指令，随后紧跟一条复位指令
    # The table line is preceded by a bold/double-size instruction and followed
    # by a reset instruction.
    before = recorder.events[table_index - 1]
    after = recorder.events[table_index + 1]
    assert before == ("set", {"bold": True, "double_width": True, "double_height": True})
    assert after == ("set", {"bold": False, "double_width": False, "double_height": False})
    assert recorder.events[-1] == ("cut", None)


def test_counter_ticket_is_not_emphasized(
    data_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """柜台单不得发送任何样式指令，全部按默认字号打印。

    The counter ticket must not send any style instruction; every line is
    printed at the default size.
    """
    printer_service.get_config().printer.mode = "network"
    recorder = _install_recording_printer(monkeypatch)

    text = render_counter_ticket(_order_view(), "我的小店", 58)
    printer_service._do_print(printer_service.get_config().printer, text, "counter")

    assert all(kind != "set" for kind, _ in recorder.events)
    assert recorder.events[-1] == ("cut", None)
