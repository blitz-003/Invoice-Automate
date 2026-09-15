import threading
import time
from pathlib import Path

import pytest
import uvicorn

from app.processing.processor import InvoiceProcessor
from app.repositories.job_repository import InvoiceRepository, JobRepository, ReviewRepository

FAKE_YAML = """\
SellerInfo.SellerName: ACME
BuyerInfo.BuyerName: GLOBEX
Invoice.InvoiceNumber: INT-2024-0001
Invoice.IssueDate: 2024-04-01
Invoice.TotalAmount: '2000'
Invoice.TaxTotal: '200'
Item[1].ItemName: Consulting
Item[1].LineAmount: '2000'
"""


def _fake_complete(self, prompt, system=None):
    return FAKE_YAML


def _make_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(
        ["INVOICE INT-2024-0001", "DATE 2024/4/1", "FROM ACME", "TO GLOBEX", "TOTAL 2000"],
        start=1,
    ):
        page.insert_text((60, 60 * i), line, fontsize=12)
    doc.save(str(path))
    doc.close()


@pytest.fixture(scope="module")
def mock_accounting():
    from app.api import accounting_api

    port = 8191
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


@pytest.fixture
def processor(mock_accounting, monkeypatch):
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
    return InvoiceProcessor()


def test_intake_review_register_flow(processor, tmp_path):
    pdf = tmp_path / "invoice-a.pdf"
    _make_pdf(pdf)

    summary = processor.process_file(str(pdf), file_name="invoice-a.pdf")
    assert summary.status == "NEEDS_REVIEW"  # low model confidence -> review
    assert summary.invoice_id is not None

    inv = InvoiceRepository().get(summary.invoice_id)
    assert inv["supplier_name"] == "ACME"  # matched to PARTNER003 alias
    assert (inv["reason_codes"] or "").find("LOW_CONFIDENCE") >= 0

    # low confidence requiring human approval
    result = processor.resolve_review(1, "APPROVED", "reviewer@demo")
    assert result["ok"] is True
    assert result["status"] == "REGISTERED"
    assert result["accounting_id"]

    inv = InvoiceRepository().get(summary.invoice_id)
    assert inv["status"] == "REGISTERED"
    assert inv["accounting_id"] == result["accounting_id"]

    # accounting-level duplicate: same partner + invoice number -> 409 -> review
    pdf2 = tmp_path / "invoice-b.pdf"
    _make_pdf(pdf2)
    summary2 = processor.process_file(str(pdf2), file_name="invoice-b.pdf")
    assert summary2.status == "NEEDS_REVIEW"
    inv2 = InvoiceRepository().get(summary2.invoice_id)
    assert "DUPLICATE_INVOICE" in (inv2["reason_codes"] or "")

    # approving the duplicate keeps it on review (accounting still rejects)
    review = ReviewRepository().get_for_invoice(summary2.invoice_id)
    result2 = processor.resolve_review(review["id"], "APPROVED", "reviewer@demo")
    assert result2["ok"] is True
    assert result2["status"] != "REGISTERED"


def test_file_deduplication(processor, tmp_path):
    pdf = tmp_path / "same.pdf"
    _make_pdf(pdf)
    processor.process_file(str(pdf), file_name="same.pdf")
    second = processor.process_file(str(pdf), file_name="same.pdf")
    assert second.success is False
    assert second.status == "REJECTED"
    assert any(e["kind"] == "DUPLICATE_FILE" for e in second.errors)
    assert second.original_job_id is not None


def test_job_repo_rows(processor, tmp_path):
    pdf = tmp_path / "row.pdf"
    _make_pdf(pdf)
    summary = processor.process_file(str(pdf), file_name="row.pdf")
    job = JobRepository().get(summary.job_id)
    assert job is not None
    assert job["status"] == summary.status
    assert job["file_name"] == "row.pdf"
    assert job["error_code"] is None