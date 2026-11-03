"""系统设置相关的 Pydantic 模型。

Pydantic schemas for system settings.
"""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# 合法的打印机模式枚举 / Allowed printer modes
_ALLOWED_PRINTER_MODES = ("mock", "network", "usb")
# 合法的纸张宽度枚举（毫米）/ Allowed paper widths in mm
_ALLOWED_PAPER_WIDTHS = (58, 80)
# 店铺名称最大长度 / Max shop name length
_MAX_SHOP_NAME_LENGTH = 32


class PrinterSettings(BaseModel):
    """打印机设置模型（读取输出用）。

    Printer settings schema (used for read output).
    """

    # 打印机连接模式：mock / network / usb / Printer mode: mock / network / usb
    mode: str = "mock"
    # 网口打印机 IP / Network printer host
    host: str = "192.168.1.200"
    # 网口打印机端口 / Network printer port
    port: int = 9100
    # USB 厂商 ID / USB vendor id
    usbVendorId: Optional[int] = None
    # USB 产品 ID / USB product id
    usbProductId: Optional[int] = None
    # 纸张宽度（毫米）：58 / 80 / Paper width in mm: 58 / 80
    paperWidth: int = 58


class PrinterSettingsUpdate(BaseModel):
    """打印机设置的部分更新输入模型（全部字段可选）。

    Partial printer-settings update schema (all fields optional). Field-level
    and cross-field validation rejects illegal printer configurations early.
    """

    # 打印机连接模式 / Printer mode
    mode: Optional[str] = None
    # 网口打印机 IP / Network printer host
    host: Optional[str] = None
    # 网口打印机端口，取值范围 1..65535 / Network printer port, 1..65535
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    # USB 厂商 ID（正整数）/ USB vendor id (positive integer)
    usbVendorId: Optional[int] = Field(default=None, ge=1)
    # USB 产品 ID（正整数）/ USB product id (positive integer)
    usbProductId: Optional[int] = Field(default=None, ge=1)
    # 纸张宽度（毫米）/ Paper width in mm
    paperWidth: Optional[int] = None

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: Optional[str]) -> Optional[str]:
        """校验打印机模式是否合法。

        Validate that the printer mode is one of mock / network / usb.

        :param value: 待校验的模式 / mode value to validate
        :return: 归一化（去空格转小写）后的模式 / normalized mode
        """
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in _ALLOWED_PRINTER_MODES:
            raise ValueError(f"打印机模式非法：{value!r}（仅支持 mock / network / usb）")
        return normalized

    @field_validator("paperWidth")
    @classmethod
    def _validate_paper_width(cls, value: Optional[int]) -> Optional[int]:
        """校验纸张宽度是否合法（仅 58 / 80）。

        Validate that the paper width is 58 or 80.

        :param value: 待校验的纸张宽度 / paper width to validate
        :return: 校验通过的纸张宽度 / validated paper width
        """
        if value is None:
            return value
        if value not in _ALLOWED_PAPER_WIDTHS:
            raise ValueError(f"纸张宽度非法：{value}（仅支持 58 / 80）")
        return value

    @model_validator(mode="after")
    def _validate_cross_fields(self) -> "PrinterSettingsUpdate":
        """跨字段校验：网口模式下 host 不能为空。

        Cross-field validation: the host must not be blank in network mode.

        :return: 自身 / self
        """
        if self.mode == "network" and self.host is not None and not self.host.strip():
            raise ValueError("网口模式下打印机 IP/主机名不能为空")
        return self


class SettingsOut(BaseModel):
    """设置读取的输出模型。

    Settings output schema.
    """

    # 店铺名称 / Shop name
    shopName: str
    # 服务端口 / Server port
    serverPort: int
    # 是否打印柜台小票 / Whether to print the counter ticket
    printCounterTicket: bool
    # 是否打印厨房小票 / Whether to print the kitchen ticket
    printKitchenTicket: bool
    # 打印机设置 / Printer settings
    printer: PrinterSettings


class SettingsUpdate(BaseModel):
    """设置更新的输入模型（全部字段可选）。

    Settings update input schema (all fields optional).
    """

    # 店铺名称（去空格后非空，长度 ≤ 32）/ Shop name (non-blank after trim, ≤ 32)
    shopName: Optional[str] = None
    # 服务端口（1024..65535）/ Server port (1024..65535)
    serverPort: Optional[int] = Field(default=None, ge=1024, le=65535)
    # 是否打印柜台小票 / Whether to print the counter ticket
    printCounterTicket: Optional[bool] = None
    # 是否打印厨房小票 / Whether to print the kitchen ticket
    printKitchenTicket: Optional[bool] = None
    # 打印机设置（部分字段更新）/ Printer settings (partial update)
    printer: Optional[PrinterSettingsUpdate] = None

    @field_validator("shopName")
    @classmethod
    def _validate_shop_name(cls, value: Optional[str]) -> Optional[str]:
        """校验店铺名称：去空格后非空且长度不超过 32。

        Validate the shop name: non-blank after trimming and at most 32 chars.

        :param value: 待校验的店铺名称 / shop name to validate
        :return: 去空格后的店铺名称 / trimmed shop name
        """
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("店铺名称不能为空")
        if len(stripped) > _MAX_SHOP_NAME_LENGTH:
            raise ValueError(f"店铺名称长度不能超过 {_MAX_SHOP_NAME_LENGTH} 个字符")
        return stripped


class SettingsUpdateResult(SettingsOut):
    """设置更新的输出模型（在设置内容之外附带是否需要重启）。

    Settings update result schema (settings payload plus a restart-required
    flag). ``restartRequired`` is ``True`` only when ``serverPort`` changed,
    because only the port change needs a program restart.
    """

    # 是否需要重启才能生效（仅端口变更时为 True）/ Whether a restart is required
    restartRequired: bool = False


class TestPrintResult(BaseModel):
    """测试打印结果模型。

    Test print result schema.
    """

    # 是否成功 / Whether the test print succeeded
    ok: bool
    # 结果说明（中文可读原因或建议）/ Result message (readable reason or hint)
    message: str


class SettingsStatus(BaseModel):
    """运行状态信息模型（供设置页展示）。

    Runtime status schema (shown on the settings page).
    """

    # 当前服务端口 / Current server port
    port: int
    # 店铺名称 / Shop name
    shopName: str
    # 是否为模拟打印机 / Whether the printer is in mock mode
    isMockPrinter: bool
    # 当前打印机模式 / Current printer mode
    printerMode: str
    # 局域网访问地址集合 / LAN access URLs
    lanUrls: Dict[str, str]
    # 本机（127.0.0.1）访问地址集合 / Localhost access URLs
    localUrls: Dict[str, str] = Field(default_factory=dict)
    # 数据库文件路径 / Database file path
    dbPath: str
    # 打印输出目录 / Printed output directory
    printedDir: str
    # 应用版本号 / Application version
    version: str
