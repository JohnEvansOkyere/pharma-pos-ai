"""
Utilities for consistent fixed-scale money handling.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Union


MoneyLike = Union[Decimal, int, float, str]
MONEY_QUANTUM = Decimal("0.01")


def to_decimal(value: Optional[MoneyLike], *, allow_none: bool = False) -> Optional[Decimal]:
    """Convert application money input to Decimal without binary float artifacts."""
    if value is None:
        if allow_none:
            return None
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_money(value: MoneyLike) -> Decimal:
    """Round money values using standard financial half-up rounding."""
    return to_decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
