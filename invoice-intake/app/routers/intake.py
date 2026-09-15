from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.processing.processor import InvoiceProcessor
from app.repositories.database import init_db
from app.repositories.job_repository import AuditRepository, InvoiceRepository, JobRepository, ReviewRepository
from app.utils.logging import get_logger

router = APIRouter(tags=["intake"])
logger = get_logger("intake")


@router.post("/api/intake")
async def intake(
    file: UploadFile = File(...),
    field: str = "",
    uploadURL: str = "",
    fileName: str = "",
):
    """Accept an invoice file (multipart), journal the job, run the pipeline."""
    return await process_upload(file, field=field, upload_url=uploadURL, file_name=fileName)


async def process_upload(
    file: UploadFile,
    *,
    field: str = "",
    upload_url: str = "",
    file_name: str = "",
) -> JSONResponse:
    settings = get_settings()
    ext = Path(file.filename or "").suffix.lower() or ".pdf"
    tmp_dir = Path(settings.storage_root) / "in" / f"_upload_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    target = tmp_dir / f"source{ext}"
    with target.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)

    name = (file_name or file.filename or target.name)
    try:
        summary = InvoiceProcessor().process_file(
            str(target),
            file_name=Path(name).name,
            field=field,
            upload_url=upload_url,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    payload = summary.__dict__
    return JSONResponse(status_code=200, content=payload)


@router.get("/api/jobs")
def list_jobs():
    jobs = JobRepository().list_recent(limit=50)
    return {
        "jobs": [
            {
                "id": j["id"],
                "file_name": j["file_name"],
                "status": j["status"],
                "error_code": j["error_code"],
                "error_message": j["error_message"],
                "created_at": j["created_at"],
                "updated_at": j["updated_at"],
            }
            for j in jobs
        ]
    }


@router.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = JobRepository().get(job_id)
    if job is None:
        raise HTTPException(404, f"job {job_id} not found")
    return dict(job)


@router.post("/api/jobs/{job_id}/reprocess")
def reprocess_job(job_id: str):
    """Re-run the pipeline for a job from its stored original document."""
    if JobRepository().get(job_id) is None:
        raise HTTPException(404, f"job {job_id} not found")
    summary = InvoiceProcessor().reprocess(job_id)
    return JSONResponse(status_code=200, content=summary.__dict__)


@router.post("/api/jobs/{job_id}/stop")
def stop_job(job_id: str):
    """Stop a stuck job and mark it FAILED (CANCELLED_BY_USER)."""
    result = InvoiceProcessor().stop(job_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("message", "job not found"))
    return result


@router.get("/api/jobs/{job_id}/document")
def job_document(job_id: str):
    settings = get_settings()
    job_dir = Path(settings.storage_root) / "in" / job_id
    if not job_dir.exists():
        raise HTTPException(404, f"job {job_id} not found")

    pages = []
    pages_dir = job_dir / "pages"
    if pages_dir.exists():
        for f in sorted(pages_dir.glob("page*")):
            pages.append({"file": f.name, "url": f"/files/in/{job_id}/pages/{f.name}"})
    sources = [{"file": f.name, "url": f"/files/in/{job_id}/{f.name}"}
               for f in job_dir.glob("source*")]

    manifest = {}
    manifest_path = job_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest = {}

    result = {}
    out_file = manifest.get("results.out_file")
    if out_file and Path(out_file).exists():
        try:
            result = json.loads(Path(out_file).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            result = {}

    pipeline_log = []
    log_path = job_dir / "pipeline.log.json"
    if log_path.exists():
        try:
            pipeline_log = json.loads(log_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pipeline_log = []

    return {
        "job_id": job_id,
        "manifest": manifest,
        "result": result,
        "pages": pages,
        "sources": sources,
        "log": pipeline_log,
    }


@router.get("/api/invoices")
def list_invoices(status: str = ""):
    repo = InvoiceRepository()
    if status:
        invoices = repo.list_by_status(status)
    else:
        invoices = repo.list_recent(limit=100)
    for row in invoices:
        row["lines"] = repo.get_lines(row["id"])
    return {"count": len(invoices), "invoices": invoices}


@router.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: str):
    repo = InvoiceRepository()
    invoice = repo.get(invoice_id)
    if invoice is None:
        raise HTTPException(404, f"invoice {invoice_id} not found")
    invoice["lines"] = repo.get_lines(invoice_id)
    invoice["audit"] = AuditRepository().list_for_invoice(invoice_id)
    invoice["review"] = ReviewRepository().get_for_invoice(invoice_id)
    return invoice


@router.get("/api/jobs/{job_id}/evidence")
def job_evidence(job_id: str):
    settings = get_settings()
    tokens_path = Path(settings.storage_root) / "in" / job_id / "ocr_tokens.json"
    if not tokens_path.exists():
        raise HTTPException(404, f"no evidence for job {job_id}")
    try:
        tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(500, f"evidence unreadable: {exc}") from exc
    return {"job_id": job_id, "tokens": tokens}


@router.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: str):
    repo = InvoiceRepository()
    invoice = repo.get(invoice_id)
    if invoice is None:
        raise HTTPException(404, f"invoice {invoice_id} not found")
    job_id = invoice.get("job_id")
    repo.delete(invoice_id)
    if job_id:
        _delete_job_files(job_id)
        JobRepository().delete(job_id)
    return {"ok": True, "invoice_id": invoice_id}


@router.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    repo = JobRepository()
    if repo.get(job_id) is None:
        raise HTTPException(404, f"job {job_id} not found")
    repo.delete(job_id)
    _delete_job_files(job_id)
    return {"ok": True, "job_id": job_id}


def _delete_job_files(job_id: str) -> None:
    job_dir = Path(get_settings().storage_root) / "in" / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)


@router.get("/api/review")
def review_queue():
    repo = ReviewRepository()
    invs = InvoiceRepository()
    jobs = JobRepository()
    items = []
    for item in repo.list_pending():
        invoice = invs.get(item["invoice_id"]) or {}
        job = jobs.get(invoice.get("job_id") or "") or {} if invoice else {}
        item = dict(item)
        item["invoice"] = {
            "id": invoice.get("id"),
            "job_id": invoice.get("job_id"),
            "file_name": job.get("file_name"),
            "supplier_name": invoice.get("supplier_name"),
            "invoice_number": invoice.get("invoice_number"),
            "total_amount": invoice.get("total_amount"),
            "issue_date": invoice.get("issue_date"),
            "confidence": invoice.get("confidence"),
            "status": invoice.get("status"),
        }
        item["lines"] = invs.get_lines(item["invoice_id"])
        items.append(item)
    return {"count": len(items), "items": items}


@router.post("/api/review/{review_id}/approve")
def approve_review(review_id: int, reviewer: str = "", comment: str = ""):
    result = InvoiceProcessor().resolve_review(
        review_id, "APPROVED", reviewer or None, comment or None
    )
    if not result.get("ok"):
        if result.get("error_code"):
            raise HTTPException(502, result.get("message", "accounting registration failed"))
        raise HTTPException(404, result.get("message", "review item not found"))
    return result


@router.post("/api/review/{review_id}/reject")
def reject_review(review_id: int, reviewer: str = "", comment: str = ""):
    result = InvoiceProcessor().resolve_review(
        review_id, "REJECTED", reviewer or None, comment or None
    )
    if not result.get("ok"):
        raise HTTPException(404, result.get("message", "review item not found"))
    return result


@router.patch("/api/invoices/{invoice_id}/lines")
def edit_invoice_lines(invoice_id: str, body: dict):
    repo = InvoiceRepository()
    invoice = repo.get(invoice_id)
    if invoice is None:
        raise HTTPException(404, f"invoice {invoice_id} not found")
    lines = body.get("lines")
    if not isinstance(lines, list):
        raise HTTPException(400, "lines must be a list")
    old = repo.get_lines(invoice_id)
    repo.upsert_lines(invoice_id, lines)
    AuditRepository().add(
        invoice_id, "lines", len(old), len(lines),
        body.get("reviewer"), body.get("reason") or "line items updated",
    )
    return {"ok": True, "line_count": len(lines)}


@router.patch("/api/invoices/{invoice_id}/fields/{field_name}")
def edit_invoice_field(invoice_id: str, field_name: str, body: dict):
    if field_name not in {"supplier_name", "invoice_number", "issue_date", "due_date",
                          "subtotal", "tax_amount", "total_amount", "currency"}:
        raise HTTPException(400, f"field {field_name} is not editable")
    result = InvoiceProcessor().edit_field(
        invoice_id, field_name, str(body.get("value", "")),
        reviewer=body.get("reviewer"), reason=body.get("reason"),
    )
    if not result.get("ok"):
        raise HTTPException(404, result.get("message", "invoice not found"))
    return result


@router.get("/api/dashboard")
def dashboard():
    inv = InvoiceRepository()
    return {
        "jobs_total": len(JobRepository().list_recent(limit=10_000)),
        "invoice_status": inv.count_by_status(),
        "pending_review": len(ReviewRepository().list_pending()),
        "recent_jobs": [
            {
                "id": j["id"], "file_name": j["file_name"], "status": j["status"],
                "created_at": j["created_at"],
            }
            for j in JobRepository().list_recent(limit=10)
        ],
    }