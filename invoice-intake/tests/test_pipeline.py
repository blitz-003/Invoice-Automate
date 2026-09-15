import tempfile
from pathlib import Path

import pytest


class FakeLLM:
    """Returns a canned YAML extraction, independent of the prompt."""

    def __init__(self):
        self.calls: list[str] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append(prompt)
        return FAKE_YAML

    def vision_complete(self, prompt: str, image_paths: list[str]) -> str:
        self.calls.append(prompt)
        return FAKE_YAML


FAKE_YAML = """\
SellerInfo.SellerName: ACME CORPORATION
SellerInfo.SellerAddress: Tokyo Chuo-ku 1-2-3
BuyerInfo.BuyerName: GLOBEX TRADING
BuyerInfo.BuyerAddress: Osaka Kita-ku 4-5-6
Invoice.InvoiceNumber: INV-2024-0001
Invoice.IssueDate: 2024-04-01
Invoice.DueDate: 2024-05-01
Invoice.TotalAmount: '1200'
Invoice.TaxTotal: '120'
Item[1].ItemName: Web hosting
Item[1].Quantity: '1'
Item[1].UnitPrice: '1200'
Item[1].LineAmount: '1200'
"""


def _make_text_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    lines = [
        "INVOICE  INV-2024-0001",
        "DATE: 2024/4/1    DUE: 2024/5/1",
        "FROM: ACME CORPORATION  Tokyo Chuo-ku 1-2-3",
        "TO: GLOBEX TRADING  Osaka Kita-ku 4-5-6",
        "1 x Web hosting  @ 1200    1200",
        "TOTAL 1200   TAX 120",
    ]
    y = 100
    for line in lines:
        page.insert_text((60, y), line, fontsize=12)
        y += 25
    doc.save(str(path))
    doc.close()


@pytest.fixture()
def text_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "invoice.pdf"
    _make_text_pdf(p)
    return p


def test_pipeline_text_pdf_success(text_pdf, monkeypatch):
    from app.services.llm_clients import LLMClient

    fake = FakeLLM()
    monkeypatch.setattr(LLMClient, "complete", fake.complete)
    monkeypatch.setattr(LLMClient, "vision_complete", fake.vision_complete)

    from app.models.ocr import OCRValidationResult
    from app.services.ocr_validator import OCRValidator

    monkeypatch.setattr(
        OCRValidator,
        "validate",
        lambda self, result: OCRValidationResult(
            reliable=True,
            confidence=1.0,
            reasons=[],
            garbage_ratio=0.0,
            anchor_hits=3,
            has_numbers=True,
            has_date_like=True,
            has_total_like=True,
        ),
    )

    from app.pipeline.pipeline import run_pipeline

    result = run_pipeline("job-smoke", str(text_pdf), field="1")
    response = result.response
    assert response.success is True, response.errors
    assert response.invoice is not None
    fields = {f.name: f.value for f in response.invoice.resolved_fields}
    assert fields["Invoice.InvoiceNumber"] == "INV-2024-0001"
    assert fields["Invoice.TotalAmount"] == "1200"
    rows = {r.key: r.fields for r in response.invoice.output_rows}
    item_rows = [f for k, f in rows.items() if k.startswith("Item")]
    assert item_rows and item_rows[0]["ItemName"] == "Web hosting"
    assert any(k == "Total" for k in rows)


def test_pipeline_rejects_empty_file(tmp_path, monkeypatch):
    from app.pipeline.pipeline import run_pipeline

    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    result = run_pipeline("job-empty", str(empty))
    assert result.response.success is False
    kinds = [e["kind"] for e in result.response.errors]
    assert "EMPTY_FILE" in kinds


def test_pipeline_rejects_bad_extension(tmp_path, monkeypatch):
    from app.pipeline.pipeline import run_pipeline

    bad = tmp_path / "notes.txt"
    bad.write_text("hello", encoding="utf-8")
    result = run_pipeline("job-txt", str(bad))
    assert result.response.success is False
    kinds = [e["kind"] for e in result.response.errors]
    assert "INVALID_FILETYPE" in kinds


def test_pipeline_rejects_corrupt_pdf(tmp_path, monkeypatch):
    from app.pipeline.pipeline import run_pipeline

    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.4 this is not really a pdf" + b"\x00" * 64)
    result = run_pipeline("job-corrupt", str(bad))
    assert result.response.success is False
    assert any(e["kind"] in ("INVALID_PDF", "EMPTY_FILE") for e in result.response.errors)


def test_pipeline_duplicate_flag_on_second_run(text_pdf, tmp_path, monkeypatch):
    from app.services.llm_clients import LLMClient

    fake = FakeLLM()
    monkeypatch.setattr(LLMClient, "complete", fake.complete)
    monkeypatch.setattr(LLMClient, "vision_complete", fake.vision_complete)

    from app.models.ocr import OCRValidationResult
    from app.services.ocr_validator import OCRValidator

    monkeypatch.setattr(
        OCRValidator,
        "validate",
        lambda self, result: OCRValidationResult(
            reliable=True, confidence=1.0, reasons=[], garbage_ratio=0.0,
            anchor_hits=3, has_numbers=True, has_date_like=True, has_total_like=True,
        ),
    )

    from app.pipeline.pipeline import run_pipeline

    first = run_pipeline("job-dup-1", str(text_pdf)).response
    assert first.success is True
    second = run_pipeline("job-dup-2", str(text_pdf)).response
    assert second.success is True
    assert second.duplicate is True
    assert second.invoice is not None and second.invoice.duplicate is True
    kinds = [e["kind"] for e in second.errors]
    assert "DUPLICATE" in kinds