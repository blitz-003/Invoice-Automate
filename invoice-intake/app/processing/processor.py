from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field as dc_field
from datetime import date
from pathlib import Path
from typing import Optional

from app.clients.accounting_client import AccountingClient, AccountingAPIError
from app.config import get_settings
from app.models.invoice import AccountingInvoiceRequest, AccountingResult, Partner, PartnerMatch
from app.models.job import ExtractionMode, JobStatus, ReasonCode
from app.models.responses import ApiRunResponse, FinalInvoice
from app.pipeline.pipeline import run_pipeline
from app.repositories.database import init_db
from app.repositories.job_repository import (
    AuditRepository,
    InvoiceRepository,
    JobRepository,
    ReviewRepository,
)
from app.services.business_validators import validate_business
from app.services.confidence import score_confidence
from app.services.file_validator import validate_file
from app.services.partner_resolver import PartnerMatcher
from app.services.tax_resolver import tax_code_for_rate
from app.utils.hashing import sha256_file
from app.utils.logging import get_logger
from app.utils.normalization import parse_int

logger = get_logger("processor")

_HARD_REJECT_CODES = {
    "NOT_AN_INVOICE", "IMAGE_UNREADABLE", "DOCUMENT_NOT_DETECTED", "IMAGE_CUTOFF",
    "INVALID_FILETYPE", "INVALID_PDF", "EMPTY_FILE", "EXTRACTION_FAILED",
    "VISION_FAILED", "OCR_FAILED",
}

_OCR_TEXT_LOG = re.compile(r"confidence=([0-9.]+)")


@dataclass
class ProcessSummary:
    job_id: str
    success: bool = True
    status: str = ""
    invoice_id: Optional[str] = None
    accounting_id: Optional[str] = None
    duplicate: bool = False
    original_job_id: Optional[str] = None
    reason_codes: list[str] = dc_field(default_factory=list)
    errors: list[dict] = dc_field(default_factory=list)
    log: list[str] = dc_field(default_factory=list)
    invoice: Optional[dict] = None


class InvoiceProcessor:
    """Outer orchestration: journal a job through SQLite and decide register/review."""

    def __init__(self, accounting: Optional[AccountingClient] = None):
        init_db()
        self.accounting = accounting or AccountingClient()
        self.jobs = JobRepository()
        self.invoices = InvoiceRepository()
        self.reviews = ReviewRepository()
        self.audit = AuditRepository()

    # ------------------------------------------------------------- public
    def process_file(
        self,
        file_path: str,
        *,
        file_name: str = "",
        field: str = "",
        upload_url: str = "",
    ) -> ProcessSummary:
        file_hash = sha256_file(file_path)
        existing = self.jobs.find_by_hash(file_hash)
        if existing is not None:
            return self._duplicate_file(file_path, file_name, file_hash, existing["id"])

        job_id = self.jobs.create(file_name or file_path, file_hash, file_path)
        validation = validate_file(file_path)

        settings = get_settings()
        src = Path(file_path)
        persist_dir = Path(settings.storage_root) / "in" / job_id
        persist_dir.mkdir(parents=True, exist_ok=True)
        stored_src = persist_dir / f"source{src.suffix.lower() or '.bin'}"
        if stored_src != src:
            stored_src.write_bytes(src.read_bytes())

        if not validation.valid:
            error_code = validation.error_code or "CORRUPTED_FILE"
            self.jobs.update_status(job_id, JobStatus.REJECTED,
                                    error_code=error_code, error_message=validation.message)
            return ProcessSummary(
                job_id=job_id, success=False, status="REJECTED",
                errors=[{"kind": error_code, "message": validation.message}],
                log=[f"file validation failed: {error_code}: {validation.message}"],
            )
        self.jobs.update_status(job_id, JobStatus.FILE_VALIDATED)

        status_cb = lambda s: self.jobs.update_status(job_id, JobStatus(s))
        pipeline = run_pipeline(
            job_id, file_path,
            field=field, upload_url=upload_url, file_name=file_name,
            status_cb=status_cb,
        )
        response = pipeline.response
        summary = self._finalize(job_id, response)
        self._persist_logs(job_id, summary.log)
        return summary

    def reprocess(self, job_id: str) -> ProcessSummary:
        self.jobs.delete_invoice_data(job_id)
        job = self.jobs.get(job_id)
        if job is None:
            return ProcessSummary(
                job_id=job_id, success=False, status="REJECTED",
                errors=[{"kind": "JOB_NOT_FOUND", "message": f"job {job_id} not found"}],
                log=[f"reprocess: job {job_id} not found"],
            )

        settings = get_settings()
        job_dir = Path(settings.storage_root) / "in" / job_id
        sources = sorted(job_dir.glob("source*")) if job_dir.exists() else []
        if not sources:
            return ProcessSummary(
                job_id=job_id, success=False, status="REJECTED",
                errors=[{"kind": "NO_SOURCE_FILE",
                         "message": "original document is no longer available for reprocessing"}],
                log=["reprocess: no stored source file found"],
            )

        self.jobs.update_status(job_id, JobStatus.RECEIVED)
        status_cb = lambda s: self.jobs.update_status(job_id, JobStatus(s))
        pipeline = run_pipeline(
            job_id, str(sources[0]),
            field="", upload_url="", file_name=job["file_name"],
            status_cb=status_cb,
        )
        summary = self._finalize(job_id, pipeline.response)
        self._persist_logs(job_id, summary.log)
        return summary

    @staticmethod
    def _persist_logs(job_id: str, log: list[str]) -> None:
        try:
            settings = get_settings()
            dest = Path(settings.storage_root) / "in" / job_id / "pipeline.log.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:  # pragma: no cover - best effort
            logger.warning("could not persist pipeline log for %s: %s", job_id, exc)

    def stop(self, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        if job is None:
            return {"ok": False, "message": f"job {job_id} not found"}
        self.jobs.update_status(
            job_id, JobStatus.FAILED,
            error_code="CANCELLED_BY_USER",
            error_message="Processing stopped by user.",
        )
        return {"ok": True, "job_id": job_id, "status": JobStatus.FAILED.value}

    def resolve_review(self, review_id: int, decision: str, reviewer: str | None,
                       comment: str | None = None) -> dict:
        item = None
        for pending in self.reviews.list_pending():
            if pending["id"] == review_id:
                item = pending
                break
        if item is None:
            return {"ok": False, "message": "review item not found"}
        invoice_id = item["invoice_id"]
        invoice = self.invoices.get(invoice_id)
        if invoice is None:
            return {"ok": False, "message": "invoice not found"}

        if decision == "APPROVED":
            registered = self._register_invoice(invoice)
            if registered.success or registered.error_code == "DUPLICATE_INVOICE":
                accounting_id = (registered.accounting_id
                                 or (registered.details or {}).get("existing_accounting_id"))
                self.invoices.update_invoice(
                    invoice_id, status="REGISTERED",
                    accounting_id=accounting_id,
                    reason_codes=invoice["reason_codes"],
                )
                self.reviews.resolve(review_id, "APPROVED", reviewer, comment)
                self.audit.add(invoice_id, "registration", invoice.get("accounting_id"),
                               accounting_id, reviewer, "review approved")
                return {
                    "ok": True,
                    "status": "REGISTERED",
                    "accounting_id": accounting_id,
                    "duplicate": registered.error_code == "DUPLICATE_INVOICE",
                    "error": registered.error_message,
                }
            return {
                "ok": False,
                "error_code": registered.error_code or "ACCOUNTING_REJECTED",
                "message": registered.error_message or "accounting registration failed",
            }
        self.reviews.resolve(review_id, "REJECTED", reviewer, comment)
        self.invoices.update_invoice(invoice_id, status="REJECTED")
        self.audit.add(invoice_id, "review", item["status"], "REJECTED",
                       reviewer, comment or "review rejected")
        return {"ok": True, "status": "REJECTED"}

    def edit_field(self, invoice_id: str, field_name: str, new_value: str,
                   reviewer: str | None = None,
                   reason: str | None = None) -> dict:
        invoice = self.invoices.get(invoice_id)
        if invoice is None:
            return {"ok": False, "message": "invoice not found"}
        old = invoice.get(field_name)
        self.invoices.update_invoice(invoice_id, **{field_name: new_value})
        self.audit.add(invoice_id, field_name, old, new_value, reviewer, reason)
        return {"ok": True, "field_name": field_name, "old_value": old, "new_value": new_value}

    # ------------------------------------------------------------- decision
    def _finalize(self, job_id: str, response: ApiRunResponse) -> ProcessSummary:
        log = list(response.log)
        errors = [
            {
                "kind": _kind_str(e.get("kind")),
                "message": e.get("message"),
                "container_id": e.get("container_id"),
                "hints": list(e.get("hints") or []),
            }
            for e in response.errors
        ]
        invoice_data = response.invoice.model_dump(mode="json") if response.invoice else None

        if response.invoice is None or not response.success:
            hard = [e for e in errors if e.get("kind") in _HARD_REJECT_CODES]
            if hard or response.invoice is None:
                codes = [e["kind"] for e in hard]
                self.jobs.update_status(job_id, JobStatus.REJECTED,
                                        error_code=codes[0] if codes else "UNABLE_TO_EXTRACT",
                                        error_message=errors[0].get("message") if errors else "")
                return ProcessSummary(job_id=job_id, success=False, status="REJECTED",
                                      invoice_id=None, reason_codes=codes,
                                      errors=errors, log=log, invoice=invoice_data)

        mapped = self._map_invoice(job_id, response)
        if mapped is None:
            self.jobs.update_status(job_id, JobStatus.REJECTED,
                                    error_code="SCHEMA_INVALID",
                                    error_message="No invoice fields available after extraction.")
            return ProcessSummary(job_id=job_id, success=False, status="REJECTED",
                                  reason_codes=["SCHEMA_INVALID"], errors=errors,
                                  log=log, invoice=invoice_data)

        reasons, needs_review_extra = self._score(mapped, response)
        conf = score_confidence([f.confidence for f in
                                 (response.invoice.resolved_fields if response.invoice else [])])
        needs_review = conf.needs_review or needs_review_extra or bool(
            response.invoice and response.invoice.metadata_review)
        if conf.needs_review and "LOW_CONFIDENCE" not in reasons:
            reasons.append("LOW_CONFIDENCE")

        invoice_id = str(uuid.uuid4())
        evidence = self._evidence_json(response.invoice)
        mode, ocr_conf = self._extraction_meta(response.log)
        self.invoices.create(
            invoice_id, job_id,
            status="NEEDS_REVIEW" if needs_review else "REGISTERING",
            extracted=mapped["extracted_json"],
            invoice_data=mapped["data"],
            confidence=conf.score,
            extraction_mode=mode,
            ocr_confidence=ocr_conf,
            evidence_json=evidence,
            reason_codes=json.dumps(reasons, ensure_ascii=False) if reasons else None,
        )

        if needs_review:
            self.reviews.create(invoice_id, reasons or ["LOW_CONFIDENCE"], conf.score)
            status = "NEEDS_REVIEW"
            self.audit.add(invoice_id, "status", None, "NEEDS_REVIEW", "system",
                           ", ".join(reasons or ["low confidence"]))
        else:
            registered = self._register(invoice_id, mapped)
            status = registered if isinstance(registered, str) else "FAILED"
            self.audit.add(invoice_id, "registration", None,
                           self.invoices.get(invoice_id).get("accounting_id"),
                           "system", "auto-register")

        self.invoices.update_invoice(invoice_id, status=status)
        self.jobs.update_status(job_id, JobStatus(status))
        return ProcessSummary(
            job_id=job_id,
            success=status in ("REGISTERED", "NEEDS_REVIEW"),
            status=status,
            invoice_id=invoice_id,
            accounting_id=self.invoices.get(invoice_id).get("accounting_id"),
            duplicate=bool(response.duplicate),
            reason_codes=reasons,
            errors=errors,
            log=log,
            invoice=invoice_data,
        )

    # ------------------------------------------------------------- mapping
    def _map_invoice(self, job_id: str, response: ApiRunResponse) -> Optional[dict]:
        if not response.invoice:
            return None
        inv: FinalInvoice = response.invoice
        fields = {f.name: f.value for f in inv.resolved_fields if f.error is None}

        invoice_number = fields.get("Invoice.InvoiceNumber", "")
        issue_date = fields.get("Invoice.IssueDate", "")
        due_date = fields.get("Invoice.DueDate", "")
        total = parse_int(fields.get("Invoice.TotalAmount") or inv.sanitized_values.get("Invoice.TotalAmount"))
        tax = parse_int(fields.get("Invoice.TaxTotal"))
        if tax is None and fields.get("Invoice.Subtotal"):
            subtotal = parse_int(fields.get("Invoice.Subtotal"))
            if subtotal is not None and total is not None:
                tax = total - subtotal
        subtotal = parse_int(fields.get("Invoice.Subtotal"))
        if subtotal is None and total is not None and tax is not None:
            subtotal = total - tax

        supplier_name = fields.get("SellerInfo.SellerName", "")
        partner = self._match_partner(supplier_name)

        lines = self._map_lines(inv)
        return {
            "data": {
                "partner_code": partner.partner_code if partner else None,
                "supplier_name": supplier_name,
                "invoice_number": invoice_number,
                "issue_date": issue_date,
                "due_date": due_date,
                "currency": fields.get("Invoice.Currency") or "JPY",
                "subtotal": subtotal,
                "tax_amount": tax,
                "total_amount": total,
                "lines": lines,
            },
            "extracted_json": {
                "supplier_name": supplier_name,
                "supplier_registration_number": fields.get("SellerInfo.SellerTaxId"),
                "invoice_number": invoice_number,
                "issue_date": issue_date,
                "due_date": due_date,
                "currency": fields.get("Invoice.Currency") or "JPY",
                "total_amount": total,
                "tax_amount": tax,
                "subtotal": subtotal,
                "all_instances": inv.all_instances,
            },
            "partner": partner,
        }

    def _map_lines(self, inv: FinalInvoice) -> list[dict]:
        lines = []
        for row in inv.output_rows:
            if not row.key.startswith("Item"):
                continue
            f = row.fields
            qty = parse_int(f.get("Quantity"))
            unit_price = parse_int(f.get("UnitPrice"))
            amount = parse_int(f.get("LineAmount"))
            if amount is None and qty is not None and unit_price is not None:
                amount = qty * unit_price
            if amount is None:
                continue
            tax_rate = parse_int(f.get("TaxRate"))
            tax_amount = 0
            code, _ = tax_code_for_rate(tax_rate, tax_amount)
            lines.append({
                "description": f.get("ItemName") or "Line item",
                "quantity": qty,
                "unit": f.get("Unit") or None,
                "unit_price": unit_price,
                "amount": amount,
                "tax_code": code or "T10",
            })
        return lines

    def _match_partner(self, supplier_name: str) -> Optional[PartnerMatch]:
        try:
            partners = self.accounting.get_partners()
        except (AccountingAPIError, Exception):
            return None
        return PartnerMatcher(partners).match(supplier_name)

    # ------------------------------------------------------------- scoring
    def _score(self, mapped: dict, response: ApiRunResponse) -> list[str]:
        data = mapped["data"]
        reasons: list[str] = []
        partner = mapped.get("partner")

        bv = validate_business(
            issue_date=data["issue_date"] or None,
            due_date=data["due_date"] or None,
            subtotal=data["subtotal"],
            tax_amount=data["tax_amount"],
            total_amount=data["total_amount"],
            line_amount=_line_sum(data["lines"]),
        )
        reasons += bv.reason_codes
        for v in bv.critical:
            if "INVALID_DATE" in v.message and "INVALID_DATE" not in reasons:
                reasons.append("INVALID_DATE")

        if partner is None or not partner.matched:
            reasons.append("PARTNER_NOT_FOUND")
        if not _lines_have_tax_codes(data["lines"]):
            reasons.append("UNKNOWN_TAX_RATE")
        if response.invoice and response.invoice.duplicate:
            reasons.append("DUPLICATE_INVOICE")
        return _dedupe(reasons), False

    # ------------------------------------------------------------- register
    def _register(self, invoice_id: str, mapped: dict) -> str:
        invoice = self.invoices.get(invoice_id)
        data = mapped["data"]
        request = AccountingInvoiceRequest(
            partner_code=data["partner_code"] or "",
            invoice_number=data["invoice_number"] or "",
            issue_date=data["issue_date"] or "",
            due_date=data["due_date"] or "",
            currency=data["currency"] or "JPY",
            lines=[l for l in data["lines"]],
            subtotal=data["subtotal"] or 0,
            tax_amount=data["tax_amount"] or 0,
            total_amount=data["total_amount"] or 0,
        )
        try:
            res = self.accounting.create_invoice(request)
        except AccountingAPIError as exc:
            self.invoices.update_invoice(invoice_id, status="FAILED", reason_codes=exc.code)
            return "FAILED"
        if res.success:
            self.invoices.update_invoice(invoice_id, accounting_id=res.accounting_id)
            return "REGISTERED"
        return "NEEDS_REVIEW" if res.error_code == "DUPLICATE_INVOICE" else "FAILED"

    def _register_invoice(self, invoice: dict):
        data = {
            "partner_code": invoice["partner_code"] or "",
            "invoice_number": invoice["invoice_number"] or "",
            "issue_date": invoice["issue_date"] or "",
            "due_date": invoice["due_date"] or "",
            "currency": invoice["currency"] or "JPY",
            "subtotal": invoice["subtotal"] or 0,
            "tax_amount": invoice["tax_amount"] or 0,
            "total_amount": invoice["total_amount"] or 0,
            "lines": self.invoices.get_lines(invoice["id"]),
        }
        request = AccountingInvoiceRequest(**data)
        try:
            return self.accounting.create_invoice(request)
        except AccountingAPIError as exc:
            return AccountingResult(success=False, error_code=exc.code,
                                    error_message=exc.message, details=exc.details)

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _extraction_meta(logs: list[str]) -> tuple[str, Optional[float]]:
        mode = ExtractionMode.PDF_TEXT.value
        for line in logs:
            if "ocr: using PDF text layer" in line:
                mode = ExtractionMode.PDF_TEXT.value
            elif "ocr: engine=" in line:
                mode = ExtractionMode.OCR_TEXT.value
        if any("vision fallback" in line or "stage2" in line for line in logs):
            mode = ExtractionMode.VISION.value
        ocr_conf = None
        for line in logs:
            m = _OCR_TEXT_LOG.search(line)
            if m:
                ocr_conf = float(m.group(1))
        return mode, ocr_conf

    @staticmethod
    def _evidence_json(inv: Optional[FinalInvoice]) -> str:
        if inv is None:
            return "{}"
        refs = {}
        for row in inv.output_rows:
            for field, ref in (row.refs or {}).items():
                refs[f"{row.key}.{field}"] = ref
        return json.dumps(refs, ensure_ascii=False)

    def _duplicate_file(self, file_path: str, file_name: str, file_hash: str,
                        original_job_id: str) -> ProcessSummary:
        settings = get_settings()
        job_id = self.jobs.create(file_name or file_path, file_hash, file_path)
        message = f"File was already processed in job {original_job_id}."
        self.jobs.update_status(job_id, JobStatus.REJECTED,
                                error_code="DUPLICATE_FILE", error_message=message)
        return ProcessSummary(
            job_id=job_id, success=False, status="REJECTED",
            duplicate=True, original_job_id=original_job_id,
            errors=[{"kind": "DUPLICATE_FILE", "message": message}],
            log=[message],
        )


def _line_sum(lines: list[dict]) -> Optional[int]:
    if not lines:
        return None
    return sum(l["amount"] for l in lines if l.get("amount"))


def _lines_have_tax_codes(lines: list[dict]) -> bool:
    return bool(lines) and all(l.get("tax_code") for l in lines)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _kind_str(kind) -> str:
    if hasattr(kind, "value"):
        return kind.value
    if kind is None:
        return "UNKNOWN"
    return str(kind)