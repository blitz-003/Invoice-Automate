from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InvoiceLine(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str = Field(min_length=1)
    quantity: Optional[int] = None
    unit: Optional[str] = None
    unit_price: Optional[int] = None
    amount: int
    tax_code: Literal["T10", "T08"]


class Invoice(BaseModel):
    """Final, validated invoice ready for the accounting API."""

    model_config = ConfigDict(extra="ignore")

    partner_code: str
    invoice_number: str
    issue_date: date
    due_date: date
    currency: Literal["JPY"] = "JPY"
    lines: list[InvoiceLine] = Field(min_length=1)
    subtotal: int
    tax_amount: int
    total_amount: int

    @field_validator("lines")
    @classmethod
    def _lines_not_empty(cls, v: list[InvoiceLine]) -> list[InvoiceLine]:
        if not v:
            raise ValueError("at least one line is required")
        return v


class AccountingInvoiceRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    partner_code: str
    invoice_number: str
    issue_date: str
    due_date: str
    currency: Literal["JPY"] = "JPY"
    lines: list[InvoiceLine]
    subtotal: int
    tax_amount: int
    total_amount: int

    @classmethod
    def from_invoice(cls, invoice: Invoice) -> "AccountingInvoiceRequest":
        return cls(
            partner_code=invoice.partner_code,
            invoice_number=invoice.invoice_number,
            issue_date=invoice.issue_date.isoformat(),
            due_date=invoice.due_date.isoformat(),
            currency=invoice.currency,
            lines=[l.model_copy(deep=True) for l in invoice.lines],
            subtotal=invoice.subtotal,
            tax_amount=invoice.tax_amount,
            total_amount=invoice.total_amount,
        )


class Partner(BaseModel):
    model_config = ConfigDict(extra="ignore")

    partner_code: str
    name: str
    aliases: list[str] = []
    registration_no: str = ""


class TaxCode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tax_code: str
    rate: float
    label: str


class PartnerMatch(BaseModel):
    matched: bool
    partner_code: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""
    matched_name: Optional[str] = None

    @classmethod
    def no_match(cls, reason: str = "No reliable partner match") -> "PartnerMatch":
        return cls(matched=False, confidence=0.0, reason=reason)


class AccountingResult(BaseModel):
    success: bool
    accounting_id: Optional[str] = None
    status_code: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    details: Optional[dict] = None


class BBox(BaseModel):
    page: int = 1
    x: float
    y: float
    width: float
    height: float


class FieldEvidence(BaseModel):
    field: str
    value: str
    confidence: float = 1.0
    bboxes: list[BBox] = []