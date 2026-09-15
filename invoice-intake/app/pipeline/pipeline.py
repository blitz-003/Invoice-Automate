from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from app.config import get_settings
from app.models.input_errors import InputError, InputErrorKind
from app.models.resolvers import ResolutionResult
from app.models.responses import ApiRunResponse, FinalInvoice, OutputRow, ResolvedField
from app.pipeline.steps import (
    assembly,
    extraction_stage,
    preflight,
    resolution_stage,
    validation_stage,
)
from app.schema.fast_rules import load_schema
from app.services.duplicate_conflict import DuplicateConflictService
from app.services.extractor import ExtractedData
from app.services.storage import InvoiceStore, JobManifest
from app.utils.logging import get_logger
from app.utils.we import We_Requester, WH_Requester

logger = get_logger("pipeline")


class PipelineResult:
    def __init__(self, response: ApiRunResponse, manifest: JobManifest):
        self.response = response
        self.manifest = manifest


def run_pipeline(
    job_key: str,
    uploaded_file: str,
    *,
    field: str = "",
    upload_url: str = "",
    file_name: str = "",
    reviewer_overrides: Optional[dict[str, str]] = None,
    status_cb: Optional[Callable[[str], None]] = None,
) -> PipelineResult:
    log: list[str] = []
    manifest = JobManifest(job_key)
    store = InvoiceStore()
    schema = load_schema()
    response = ApiRunResponse(job_key=job_key)

    source_file = Path(uploaded_file)
    if not source_file.exists() or source_file.stat().st_size == 0:
        return _fail(job_key, manifest,
                     InputError(kind=InputErrorKind.EMPTY_FILE,
                                message="The uploaded file was empty or missing."),
                     log)

    preflight_errors, preflight_ctx = preflight.check(source_file, schema, job_key)
    if preflight_errors:
        return _fail(job_key, manifest, preflight_errors[0], log)
    if status_cb:
        status_cb("FILE_VALIDATED")

    manifest.set("document", str(source_file.name))
    manifest.set("upload_url", upload_url)
    manifest.set("field", field)
    manifest.set("file_name", file_name)

    we = We_Requester({"container_uuid": "", "submitting_entity": "", "company_name": field})
    main_file_oid = we.create_file(job_key)
    company_id = ""
    original_oid = main_file_oid
    ocr_oid = main_file_oid

    if preflight_ctx.converted_image:
        WH_Requester.requester(str(preflight_ctx.converted_image))
    manifest.set("sourcefile_oid", original_oid)

    # --- Document → pages / text -------------------------------------------
    processed, proc_errors = preflight.process_pages(preflight_ctx, schema, log)
    if proc_errors:
        return _fail_all(job_key, manifest, proc_errors, log, response)
    if status_cb:
        status_cb("QUALITY_CHECKED")

    # --- OCR (or PDF text-layer spans) + quality -----------------------------
    ocr_result, text_mode, ocr_errors = extraction_stage.ocr_and_quality(processed, log)
    quality_fatal = [
        e for e in (ocr_errors or [])
        if e.kind in (InputErrorKind.IMAGE_UNREADABLE,
                      InputErrorKind.DOCUMENT_NOT_DETECTED,
                      InputErrorKind.IMAGE_CUTOFF)
    ]
    if quality_fatal and not text_mode:
        return _fail_all(job_key, manifest, quality_fatal, log, response)
    errors_list: list[InputError] = [e for e in (ocr_errors or []) if e.kind != InputErrorKind.OCR_FAILED]
    if status_cb:
        status_cb("OCR_COMPLETED")
        status_cb("OCR_VALIDATED")
    _persist_ocr_tokens(job_key, ocr_result, processed)

    # --- LLM extraction -----------------------------------------------------
    data, secondary, extract_errors, text_reliable = extraction_stage.extract(
        schema, processed, ocr_result, text_mode, log, response
    )
    data_err = [e for e in extract_errors if e.kind != InputErrorKind.EXTRACTION_FAILED]
    if data_err and not data.header and not data.items:
        return _fail_all(job_key, manifest, extract_errors, log, response)
    errors_list = errors_list + extract_errors

    # --- Resolution ------------------------------------------------------------
    resolution: ResolutionResult = resolution_stage.resolve(schema, data, reviewer_overrides or {})
    if status_cb:
        status_cb("EXTRACTED")
        status_cb("SCHEMA_VALIDATED")

    # --- Validation ------------------------------------------------------------
    violations, violations_errors = validation_stage.validate(schema, resolution)
    errors_list += violations_errors
    if status_cb:
        status_cb("BUSINESS_VALIDATED")

    # --- Duplicates / conflicts -------------------------------------------------
    conflict_service = DuplicateConflictService(store)
    conflict_service.check(schema, resolution)
    duplicate = conflict_service.duplicate_candidate()
    if status_cb:
        status_cb("DUPLICATE_CHECKED")

    # --- Item aggregation + cross-checks -----------------------------------------
    item_rows, aggregate_note, cross_ok = resolution_stage.assemble_items(
        schema, data, resolution, log
    )
    if duplicate:
        log.append(f"duplicate: {duplicate.invoice_id} ({duplicate.reason})")
        errors_list.append(InputError(
            kind=InputErrorKind.DUPLICATE,
            message=duplicate.note,
            container_id=duplicate.invoice_id,
        ))

    # --- Final assembly -----------------------------------------------------------
    invoice, final_rows = assembly.build_final_invoice(
        schema, resolution, item_rows, job_key,
        sf_oid=original_oid, ocr_oid=ocr_oid,
        secondary=secondary,
        log=log,
    )
    invoice.duplicate = duplicate is not None
    invoice.metadata_review = bool(violations) and not duplicate
    invoice.conflicts = [a.model_dump() for a in conflict_service.conflict_anomalies()]
    response.conflicts = invoice.conflicts or []
    response.invoice = invoice
    response.log = log
    response.duplicate = bool(duplicate)
    response.metadata_review = invoice.metadata_review

    # --- Persistence ---------------------------------------------------------------
    store.save_invoice(_store_record(job_key, invoice))
    manifest.set("results.out_file", _write_draft(job_key, invoice, log))
    for e in errors_list:
        response.errors.append(e.model_dump())
    response.errors = _dedupe_errors(response.errors)

    if violations:
        log.append("strict_DTO_validation: invoice kept (rejected-for-review) with field logs")
        response.success = False
    else:
        response.success = True
    if status_cb:
        status_cb("CONFIDENCE_SCORED")
    return PipelineResult(response, manifest)


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Evidence: normalised OCR token boxes for field<-document highlighting.


def _persist_ocr_tokens(job_key: str, ocr_result, processed) -> None:
    if not ocr_result or not ocr_result.tokens:
        return
    settings = get_settings()
    dims = {p.page_number: p for p in processed.pages}
    entries: list[dict] = []
    for token in ocr_result.tokens:
        page = dims.get(token.page)
        if page is None or not page.image_width or not page.image_height:
            continue
        x, y, w, h = token.bbox
        entries.append({
            "page": token.page,
            "text": token.text,
            "confidence": round(token.confidence, 3),
            "x": round(x / page.image_width, 4),
            "y": round(y / page.image_height, 4),
            "w": round(w / page.image_width, 4),
            "h": round(h / page.image_height, 4),
        })
    if not entries:
        return
    try:
        dest = Path(settings.storage_root) / "in" / job_key / "ocr_tokens.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.warning("could not persist ocr evidence for %s", job_key)


def _store_record(job_key: str, invoice: FinalInvoice) -> dict:
    record = {"job_key": job_key, "source_id": invoice.source_id, "duplicate": invoice.duplicate}
    for field in invoice.resolved_fields:
        if not field.error:
            record[field.name] = field.value
    return record


def _write_draft(job_key: str, invoice: FinalInvoice, log: list[str]) -> str:
    import re

    from app.config import get_settings

    root = Path(get_settings().storage_root) / "out" / job_key
    root.mkdir(parents=True, exist_ok=True)
    values_path = root / "result.values"
    values_path.write_text(
        json.dumps(invoice.sanitized_values or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    draft = root / "result.json"
    draft.write_text(invoice.model_dump_json(indent=2), encoding="utf-8")
    log.append(f"result written: {draft}")
    return str(draft)


def _dedupe_errors(errors: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for e in errors:
        key = f"{e.get('kind')}|{e.get('message')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _fail(job_key: str, manifest: JobManifest, error: InputError, log: list[str]) -> PipelineResult:
    response = ApiRunResponse(job_key=job_key)
    response.errors.append(error.model_dump())
    response.success = False
    response.log = log + [f"error: {error.kind.value}: {error.message}"]
    return PipelineResult(response, manifest)


def _fail_all(
    job_key: str,
    manifest: JobManifest,
    errors: list[InputError],
    log: list[str],
    response: ApiRunResponse,
) -> PipelineResult:
    response.errors = _dedupe_errors([e.model_dump() for e in errors])
    response.success = False
    response.log = log
    return PipelineResult(response, manifest)