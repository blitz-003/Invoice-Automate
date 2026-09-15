import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.schema.fast_rules import load_schema
from app.services.extractor import ExtractedData
from app.services.llm_clients import LLMClient

FAKE_YAML = """\
SellerInfo.SellerName: ACME
BuyerInfo.BuyerName: GLOBEX
Invoice.InvoiceNumber: INV-2024-0042
Invoice.IssueDate: 2024-04-01
Invoice.TotalAmount: '2000'
Invoice.TaxTotal: '200'
Item[1].ItemName: Consulting
Item[1].LineAmount: '2000'
"""


def _fake_complete(self, prompt, system=None):
    return FAKE_YAML


@pytest.fixture()
def app(monkeypatch):
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


def test_intake_roundtrip(app, tmp_path):
    pdf = tmp_path / "invoice.pdf"
    _make_pdf(pdf)
    with TestClient(app) as client:
        with pdf.open("rb") as fh:
            resp = client.post("/api/intake?field=1", files={"file": ("invoice.pdf", fh, "application/pdf")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["invoice"] is not None
    fields = {f["name"]: f["value"] for f in body["invoice"]["resolved_fields"]}
    assert fields["Invoice.InvoiceNumber"] == "INV-2024-0042"
    assert body["duplicate"] is False


def test_jobs_listing(app, tmp_path):
    pdf = tmp_path / "invoice.pdf"
    _make_pdf(pdf)
    with TestClient(app) as client:
        with pdf.open("rb") as fh:
            client.post("/api/intake", files={"file": ("invoice.pdf", fh, "application/pdf")})
        resp = client.get("/api/jobs")
    assert resp.status_code == 200
    assert len(resp.json()["jobs"]) >= 1


def test_health(app):
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"