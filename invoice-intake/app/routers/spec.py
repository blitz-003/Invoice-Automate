"""Spec-aligned HTTP surface for the intake service.

These routes mirror the accounting-system-facing contract while backing on the
same SQLite pipeline:

    POST /api/invoices                        upload (alias of /api/intake)
    GET  /api/invoices/{invoice_id}           invoice + lines + audit + review
    POST /api/invoices/{invoice_id}/approve   approve a pending review
    POST /api/invoices/{invoice_id}/reject    reject a pending review
    PATCH /api/invoices/{invoice_id}          edit one or more fields
    GET  /api/metrics                         operational + quality metrics
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.processing.processor import InvoiceProcessor
from app.repositories.job_repository import InvoiceRepository, JobRepository, ReviewRepository
from app.routers.intake import process_upload

router = APIRouter(tags=["spec"])

_EDITABLE_FIELDS = {
    "supplier_name", "invoice_number", "issue_date", "due_date",
    "subtotal", "tax_amount", "total_amount", "currency",
}

_TERMINAL_STATUSES = {"REGISTERED", "NEEDS_REVIEW", "REJECTED", "FAILED"}
_OCR_ERRORS = {"OCR_FAILED", "VISION_FAILED", "IMAGE_UNREADABLE", "OCR_UNRELIABLE"}


class DecisionBody(BaseModel):
    reviewer: Optional[str] = None
    comment: Optional[str] = None


class PatchInvoiceBody(BaseModel):
    field: Optional[str] = None
    value: Optional[Any] = None
    fields: Optional[dict[str, Any]] = None
    reviewer: Optional[str] = None
    reason: Optional[str] = None


@router.post("/api/invoices")
async def create_invoice(
    file: UploadFile = File(...),
    field: str = "",
    uploadURL: str = "",
    fileName: str = "",
):
    """Upload an invoice file and run the intake pipeline (alias of /api/intake)."""
    return await process_upload(file, field=field, upload_url=uploadURL, file_name=fileName)


def _resolve_pending(invoice_id: str, decision: str, body: DecisionBody) -> dict:
    repo = ReviewRepository()
    invoice = InvoiceRepository().get(invoice_id)
    if invoice is None:
        raise HTTPException(404, f"invoice {invoice_id} not found")
    review = repo.get_for_invoice(invoice_id)
    if review is None:
        raise HTTPException(409, f"invoice {invoice_id} has no pending review item")
    result = InvoiceProcessor().resolve_review(
        review["id"], decision, body.reviewer or None, body.comment or None
    )
    if not result.get("ok"):
        raise HTTPException(404, result.get("message", "review item not found"))
    return result


@router.post("/api/invoices/{invoice_id}/approve")
def approve_invoice(invoice_id: str, body: Optional[DecisionBody] = None):
    """Approve the pending review for an invoice; registers it on success."""
    return _resolve_pending(invoice_id, "APPROVED", body or DecisionBody())


@router.post("/api/invoices/{invoice_id}/reject")
def reject_invoice(invoice_id: str, body: Optional[DecisionBody] = None):
    """Reject the pending review for an invoice."""
    return _resolve_pending(invoice_id, "REJECTED", body or DecisionBody())


@router.patch("/api/invoices/{invoice_id}")
def patch_invoice(invoice_id: str, body: PatchInvoiceBody):
    """Edit one (`field`/`value`) or several (`fields`) invoice fields."""
    processor = InvoiceProcessor()
    edits = body.fields or {}
    if body.field is not None:
        edits[body.field] = body.value
    if not edits:
        raise HTTPException(400, "provide 'fields' or 'field'/'value'")
    unknown = [k for k in edits if k not in _EDITABLE_FIELDS]
    if unknown:
        raise HTTPException(400, f"fields not editable: {', '.join(unknown)}")
    results = []
    for field_name, value in edits.items():
        result = processor.edit_field(
            invoice_id, field_name, str(value),
            reviewer=body.reviewer, reason=body.reason,
        )
        if not result.get("ok"):
            raise HTTPException(404, result.get("message", "invoice not found"))
        results.append(result)
    return {"ok": True, "updated": len(results), "results": results}


# ------------------------------------------------------------- metrics
def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


@router.get("/api/metrics")
def metrics():
    jobs = JobRepository().list_recent(limit=10_000)
    invs = InvoiceRepository().list_recent(limit=10_000)
    review_repo = ReviewRepository()

    job_status: dict[str, int] = {}
    terminal_min, terminal_max = None, None
    for j in jobs:
        job_status[j["status"]] = job_status.get(j["status"], 0) + 1
        if j["status"] in _TERMINAL_STATUSES:
            start, end = _parse_ts(j["created_at"]), _parse_ts(j["updated_at"])
            if start and end:
                if terminal_min is None or start < terminal_min:
                    terminal_min = start
                if terminal_max is None or end > terminal_max:
                    terminal_max = end

    invoice_status: dict[str, int] = {}
    confs: list[float] = []
    modes: dict[str, int] = {}
    dup = ocreq = 0
    for inv in invs:
        invoice_status[inv["status"]] = invoice_status.get(inv["status"], 0) + 1
        if inv.get("confidence") is not None:
            confs.append(float(inv["confidence"]))
        mode = inv.get("extraction_mode")
        if mode:
            modes[mode] = modes.get(mode, 0) + 1
        reasons = inv.get("reason_codes") or ""
        if "DUPLICATE_INVOICE" in reasons or "DUPLICATE_FILE" in reasons:
            dup += 1
        if inv.get("status") == "REJECTED" or any(
            e in reasons for e in _OCR_ERRORS
        ):
            ocreq += 1

    pending = review_repo.list_pending()
    total_jobs = len(jobs)
    total_invoices = len(invs)

    processing_seconds = None
    for j in jobs:
        if j["status"] in _TERMINAL_STATUSES:
            start, end = _parse_ts(j["created_at"]), _parse_ts(j["updated_at"])
            if start and end:
                raw = (end - start).total_seconds()
                processing_seconds = raw if processing_seconds is None else (
                    processing_seconds + raw)

    return {
        "invoices_total": total_invoices,
        "invoices_by_status": invoice_status,
        "jobs_total": total_jobs,
        "jobs_by_status": job_status,
        "extraction_modes": modes,
        "ocr_failure_count": ocreq,
        "ocr_failure_rate": round(ocreq / total_invoices, 4) if total_invoices else 0.0,
        "pending_review": len(pending),
        "review_resolved": {
            "approved": len([i for i in review_repo.list_all() if i["status"] == "APPROVED"]),
            "rejected": len([i for i in review_repo.list_all() if i["status"] == "REJECTED"]),
        },
        "duplicate_count": dup,
        "duplicate_rate": round(dup / total_invoices, 4) if total_invoices else 0.0,
        "average_confidence": round(sum(confs) / len(confs), 4) if confs else None,
        "average_processing_seconds": round(processing_seconds / total_jobs, 2) if processing_seconds else None,
        "time_window": {
            "first": terminal_min.isoformat() if terminal_min else None,
            "last": terminal_max.isoformat() if terminal_max else None,
        },
    }