"""Standalone mock of the external accounting system.

Run with:  python -m app.api.accounting_api          (default http://localhost:8080)

Endpoints (all JSON, `X-API-Key: demo-key-1234`-checked):
  GET    /health            -> { status, api_version, time }
  GET    /partners          -> partner master list
  GET    /tax-codes         -> consumption-tax codes
  POST   /invoices          -> register an invoice (409 DUPLICATE_INVOICE on repeat)
  GET    /invoices          -> list registered invoices
  DELETE /invoices          -> reset the store (demo helper)
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

API_KEY = os.environ.get("ACCOUNTING_API_KEY", "demo-key-1234")

app = FastAPI(title="Mock Accounting API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

STORE: dict[str, dict] = {}
_STORE_LOCK = {"lock": False}  # cheap process-local guard; single-threaded demo


class MockInvoiceLine(BaseModel):
    description: str = Field(min_length=1)
    quantity: Optional[int] = None
    unit: Optional[str] = None
    unit_price: Optional[int] = None
    amount: int
    tax_code: str

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("amount must be >= 0")
        return v


class MockInvoice(BaseModel):
    partner_code: str = Field(min_length=1)
    invoice_number: str = Field(min_length=1)
    issue_date: str
    due_date: str
    currency: str = "JPY"
    lines: list[MockInvoiceLine] = Field(min_length=1)
    subtotal: int = 0
    tax_amount: int = 0
    total_amount: int = 0


PARTNERS = [
    {"partner_code": "PARTNER001", "name": "株式会社サンプル商事", "aliases": ["サンプル商事", "Sample Shoji"],
     "registration_no": "T1010401012345"},
    {"partner_code": "PARTNER002", "name": "有限会社テストコーポレーション", "aliases": ["テストコーポレーション"],
     "registration_no": "T6010401999999"},
    {"partner_code": "PARTNER003", "name": "ACME Trading Co., Ltd.", "aliases": ["ACME", "ACME Trading"],
     "registration_no": ""},
]

TAX_CODES = [
    {"tax_code": "T10", "rate": 10.0, "label": "Standard tax (10%)"},
    {"tax_code": "T08", "rate": 8.0, "label": "Reduced tax (8%)"},
]


def _json_error(code: str, message: str, status: int, details: dict | None = None):
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message, "details": details or {}},
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "api_version": "1.0.0",
        "time": datetime.now(timezone.utc).isoformat(),
        "registered_invoices": len(STORE),
    }


@app.get("/partners")
def partners(x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise _json_error("ACCOUNTING_AUTH_ERROR", "Invalid API key", 401)
    return {"data": {"partners": PARTNERS}}


@app.get("/tax-codes")
def tax_codes(x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise _json_error("ACCOUNTING_AUTH_ERROR", "Invalid API key", 401)
    return {"data": {"tax_codes": TAX_CODES}}


@app.post("/invoices", status_code=201)
def create_invoice(invoice: MockInvoice, request: Request,
                   flaky: bool = Query(default=False),
                   x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise _json_error("ACCOUNTING_AUTH_ERROR", "Invalid API key", 401)
    if flaky and len(STORE) % 3 == 0:
        raise _json_error("ACCOUNTING_SERVICE_ERROR", "Simulated transient failure", 503)

    key = (invoice.partner_code, invoice.invoice_number)
    for existing in STORE.values():
        if (existing["partner_code"], existing["invoice_number"]) == key:
            raise _json_error(
                "DUPLICATE_INVOICE",
                f"Invoice {invoice.invoice_number} for {invoice.partner_code} already registered "
                f"(accounting_id={existing['accounting_id']}).",
                409,
                details={"existing_accounting_id": existing["accounting_id"]},
            )

    accounting_id = f"ACC-{uuid.uuid4().hex[:10].upper()}"
    record = invoice.model_dump()
    record.update({
        "accounting_id": accounting_id,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    })
    STORE[accounting_id] = record
    return {"data": {"accounting_id": accounting_id, "registered_at": record["registered_at"]}}


@app.get("/invoices")
def list_invoices(x_api_key: str = Header(default=""), limit: int = Query(default=200)):
    if x_api_key != API_KEY:
        raise _json_error("ACCOUNTING_AUTH_ERROR", "Invalid API key", 401)
    invoices = list(STORE.values())
    return {"data": {"count": len(invoices), "invoices": invoices[:limit]}}


@app.delete("/invoices")
def reset_invoices(x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise _json_error("ACCOUNTING_AUTH_ERROR", "Invalid API key", 401)
    removed = len(STORE)
    STORE.clear()
    return {"data": {"removed": removed}}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("ACCOUNTING_PORT", "8080"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")