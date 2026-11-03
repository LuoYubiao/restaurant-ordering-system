"""金额换算工具模块。

Money conversion utility module.

系统内部统一使用「分」为单位的整数存储金额，对外接口使用保留两位小数的字符串。
Amounts are stored internally as integers in cents (fen) and exposed externally
as strings with exactly two decimal places.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Union

# 分与元的换算比例 / Conversion ratio between fen and yuan
_CENT = Decimal("100")
# 元的小数位（2 位）/ Yuan decimal places (2)
_YUAN_QUANT = Decimal("0.01")

# 允许的输入类型 / Accepted input types
MoneyLike = Union[str, int, float, Decimal]


def fen_to_yuan(fen: int) -> str:
    """把「分」转换为保留两位小数的「元」字符串。

    Convert an integer amount in fen to a yuan string with two decimals.

    :param fen: 以分为单位的整数金额 / integer amount in fen
    :return: 例如 1250 -> ``"12.50"`` / e.g. 1250 -> ``"12.50"``
    """
    return str((Decimal(int(fen)) / _CENT).quantize(_YUAN_QUANT, rounding=ROUND_HALF_UP))


def yuan_to_fen(value: MoneyLike) -> int:
    """把「元」转换为以「分」为单位的整数。

    Convert a yuan value to an integer amount in fen. ``Decimal`` is used to
    avoid binary floating point rounding errors.

    :param value: 金额，支持字符串、整数、浮点数或 Decimal（如 ``"12.50"``）
        / amount as str, int, float or Decimal (e.g. ``"12.50"``)
    :return: 以分为单位的整数 / integer amount in fen
    :raises ValueError: 输入非法（空值、非数字、NaN 等）
        / when the input is not a valid finite number
    """
    if value is None:
        raise ValueError("money value must not be None")
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid money value: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"invalid money value: {value!r}")
    fen = (amount * _CENT).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(fen)


def format_money(fen: int) -> str:
    """金额格式化（``fen_to_yuan`` 的别名）。

    Format an integer amount in fen as a yuan string (alias of
    :func:`fen_to_yuan`).

    :param fen: 以分为单位的整数金额 / integer amount in fen
    :return: 保留两位小数的元字符串 / yuan string with two decimals
    """
    return fen_to_yuan(fen)
