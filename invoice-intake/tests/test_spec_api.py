import threading
import time
import uuid
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app.repositories.job_repository import InvoiceRepository, JobRepository, ReviewRepository

FAKE_YAML = """\
SellerInfo.SellerName: ACME
BuyerInfo.BuyerName: GLOBEX
Invoice.InvoiceNumber: INV-2024-0042
Invoice.IssueDate: 2024-04-01
Invoice.DueDate: 2024-04-30
Invoice.TotalAmount: '2000'
Invoice.TaxTotal: '200'
Item[1].ItemName: Consulting
Item[1].LineAmount: '2000'
"""


def _fake_complete(self, prompt, system=None):
    return FAKE_YAML


@pytest.fixture(scope="module")
def mock_accounting():
    from app.api import accounting_api

    port = 8192
    server = uvicorn.Server(uvicorn.Config(accounting_api.app, host="127.0.0.1",
                                           port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(60):
        try:
            import httpx

            httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


@pytest.fixture()
def app(mock_accounting, monkeypatch):
    monkeypatch.setenv("ACCOUNTING_API_URL", mock_accounting)

    from app.services.llm_clients import LLMClient

    monkeypatch.setattr(LLMClient, "complete", _fake_complete)
    monkeypatch.setattr(LLMClient, "vision_complete", _fake_complete)

    from app.models.ocr import OCRValidationResult
    from app.services.ocr_validator import OCRValidator

    monkeypatch.setattr(
        OCRValidator,
        "validate",
        lambda self, result: OCRValidationResult(
            reliable=True, confidence=1.0, reasons=[], garbage_ratio=0.0,
            anchor_hits=2, has_numbers=True, has_date_like=True, has_total_like=True,
        ),
    )
    from app.main import app as fastapi_app

    return fastapi_app


def _make_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(
        ["INVOICE INV-2024-0042", "DATE 2024/4/1", "FROM ACME", "TO GLOBEX", "TOTAL 2000"],
        start=1,
    ):
        page.insert_text((60, 60 * i), line, fontsize=12)
    doc.save(str(path))
    doc.close()


def _seed_invoice(status="NEEDS_REVIEW", reason_codes='["LOW_CONFIDENCE"]') -> str:
    invoice_id = f"inv-{uuid.uuid4().hex[:12]}"
    job_id = JobRepository().create(f"{invoice_id}.pdf", "hash-" + invoice_id, "/tmp/x")
    InvoiceRepository().create(
        invoice_id, job_id, status=status, reason_codes=reason_codes,
        extraction_mode="PDF_TEXT", confidence=0.62, accounting_id=None,
        invoice_data={
            "partner_code": "PARTNER001",
            "supplier_name": "株式会社サンプル商事",
            "invoice_number": "INV-SPEC-001",
            "issue_date": "2026-01-10",
            "due_date": "2026-02-10",
            "currency": "JPY",
            "subtotal": 2000, "tax_amount": 200, "total_amount": 2200,
            "lines": [
                {"description": "Consulting", "quantity": None, "unit": "式",
                 "unit_price": None, "amount": 2000, "tax_code": "T10"},
            ],
        },
    )
    ReviewRepository().create(invoice_id, ["LOW_CONFIDENCE"], 0.62)
    return invoice_id


def test_spec_upload_alias(app, tmp_path):
    pdf = tmp_path / "invoice.pdf"
    _make_pdf(pdf)
    with TestClient(app) as client:
        with pdf.open("rb") as fh:
            resp = client.post("/api/invoices", files={"file": ("invoice.pdf", fh, "application/pdf")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    fields = {f["name"]: f["value"] for f in body["invoice"]["resolved_fields"]}
    assert fields["Invoice.InvoiceNumber"] == "INV-2024-0042"


def test_get_invoice_and_404(app):
    invoice_id = _seed_invoice()
    with TestClient(app) as client:
        resp = client.get(f"/api/invoices/{invoice_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == invoice_id
    assert body["status"] == "NEEDS_REVIEW"
    assert len(body["lines"]) == 1

    with TestClient(app) as client:
        resp = client.get("/api/invoices/does-not-exist")
    assert resp.status_code == 404


def test_approve_registers(app):
    invoice_id = _seed_invoice()
    with TestClient(app) as client:
        resp = client.post(f"/api/invoices/{invoice_id}/approve",
                           json={"reviewer": "tester@demo", "comment": "ok"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == "REGISTERED"
    assert body["accounting_id"]

    inv = InvoiceRepository().get(invoice_id)
    assert inv["status"] == "REGISTERED"
    assert inv["accounting_id"] == body["accounting_id"]


def test_approve_no_pending_conflict(app):
    invoice_id = f"inv-{uuid.uuid4().hex[:12]}"
    job_id = JobRepository().create(f"{invoice_id}.pdf", "hash-" + invoice_id, "/tmp/x")
    InvoiceRepository().create(
        invoice_id, job_id, status="REGISTERED",
        invoice_data={
            "partner_code": "PARTNER001",
            "supplier_name": "株式会社サンプル商事",
            "invoice_number": "INV-SPEC-REG-2",
            "issue_date": "2026-01-10", "due_date": "2026-02-10",
            "currency": "JPY", "subtotal": 2000, "tax_amount": 200, "total_amount": 2200,
            "lines": [{"description": "Consulting", "quantity": None, "unit": "式",
                       "unit_price": None, "amount": 2000, "tax_code": "T10"}],
        },
    )
    with TestClient(app) as client:
        resp = client.post(f"/api/invoices/{invoice_id}/approve", json={})
    assert resp.status_code != 200


def test_reject_updates_status(app):
    invoice_id = _seed_invoice()
    with TestClient(app) as client:
        resp = client.post(f"/api/invoices/{invoice_id}/reject",
                           json={"reviewer": "tester@demo", "comment": "wrong amount"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"
    assert InvoiceRepository().get(invoice_id)["status"] == "REJECTED"


def test_patch_fields(app):
    invoice_id = _seed_invoice()
    before = InvoiceRepository().get(invoice_id)
    assert before["total_amount"] == 2200

    with TestClient(app) as client:
        resp = client.patch(f"/api/invoices/{invoice_id}",
                            json={"field": "total_amount", "value": "2300",
                                  "reviewer": "tester@demo", "reason": "tax recalculated"})
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1
    assert InvoiceRepository().get(invoice_id)["total_amount"] == 2300

    with TestClient(app) as client:
        resp = client.patch(f"/api/invoices/{invoice_id}",
                            json={"fields": {"total_amount": "2400", "currency": "JPY"}})
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2
    assert InvoiceRepository().get(invoice_id)["total_amount"] == 2400

    with TestClient(app) as client:
        resp = client.patch(f"/api/invoices/{invoice_id}",
                            json={"field": "bogus", "value": "1"})
    assert resp.status_code == 400


def test_metrics_shape(app):
    _seed_invoice()
    with TestClient(app) as client:
        resp = client.get("/api/metrics")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("invoices_total", "invoices_by_status", "jobs_total",
                "extraction_modes", "pending_review", "average_confidence",
                "ocr_failure_rate", "duplicate_rate"):
        assert key in body
    assert body["invoices_total"] >= 1