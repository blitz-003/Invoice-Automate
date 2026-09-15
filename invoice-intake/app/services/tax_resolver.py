from __future__ import annotations

from typing import Optional

_RATE_TO_CODE = {10: "T10", 8: "T08"}


def tax_code_for_rate(tax_rate: int | None, tax_amount: int | None = 0) -> tuple[Optional[str], str | None]:
    """Map an LLM-provided consumption-tax rate to an accounting tax code.

    Returns (tax_code, reason_code | None). Unknown rates without any tax yield
    T10 (tax-free); unknown rates WITH tax yield None + UNKNOWN_TAX_RATE.
    """
    if tax_rate is not None and tax_rate in _RATE_TO_CODE:
        return _RATE_TO_CODE[tax_rate], None
    if tax_amount in (0, None):
        return "T10", None
    return None, "UNKNOWN_TAX_RATE"