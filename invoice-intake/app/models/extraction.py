from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtractedLine(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str
    quantity: Optional[int] = None
    unit: Optional[str] = None
    unit_price: Optional[int] = None
    amount: int
    tax_rate: Optional[int] = None


class ExtractedInvoice(BaseModel):
    """Intermediate extraction produced by the LLM (text or vision path)."""

    model_config = ConfigDict(extra="ignore")

    supplier_name: Optional[str] = None
    supplier_registration_number: Optional[str] = None

    invoice_number: Optional[str] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    currency: Optional[str] = "JPY"

    lines: list[ExtractedLine] = []
    subtotal: Optional[int] = None
    tax_amount: Optional[int] = None
    total_amount: Optional[int] = None

    notes: Optional[str] = None

    @model_validator(mode="after")
    def _normalize_dates(self) -> "ExtractedInvoice":
        from app.utils.normalization import parse_japanese_date

        if self.issue_date:
            parsed = parse_japanese_date(self.issue_date)
            if parsed:
                self.issue_date = parsed.isoformat()
        if self.due_date:
            parsed = parse_japanese_date(self.due_date)
            if parsed:
                self.due_date = parsed.isoformat()
        return self

    @property
    def issue_date_obj(self) -> Optional[date]:
        return parse_iso(self.issue_date)

    @property
    def due_date_obj(self) -> Optional[date]:
        return parse_iso(self.due_date)


def parse_iso(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        from datetime import date as _date

        return _date.fromisoformat(str(value)[:10])
    except ValueError:
        return None