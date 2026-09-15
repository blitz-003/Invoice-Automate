# Invoice Intake — submission notes

This document maps the implementation to the original requirements document.
For every behavior I state **how** it is realized in code and **where**
(`path:line` or module name). Honest caveats are called out at the end.

## 1. API (from gateway)

`app/routers/intake.py`
- `POST /api/intake?field=1&uploadURL=...&fileName=...`, multipart `file`
  (FastAPI `UploadFile`), full pipeline runs synchronously and returns the
  result or rejection body in one response. `field` is emitted to the
  We requester search attributes (`app/pipeline/pipeline.py`).
- `GET /api/jobs`, `GET /api/jobs/{job_key}`, and
  `POST /api/jobs/{job_key}/reprocess` (empty-change re-populate flow with
  reviewer field overrides persisted to `overrides.json`).
- Streamed PDFs are accepted; that is, we take a bytes blob — we do not embed
  streaming a multipart in the prototype, but `UploadFile` is lazily read
  (`shutil.copyfileobj`) so it behaves identically for large files.
- Auto-approval/review routing: reviewer decision splice is applied via the
  `reprocess` override path; confidence from `app/models/resolvers.py`
  (`CleanedValue.confidence`) decides `invoice.metadata_review`.

## 2. Validation (なのる/NaN)

`app/pipeline/steps/preflight.py`
- Missing/zero-byte file → `EMPTY_FILE`.
- Unsupported type → `INVALID_FILETYPE` (`ALLOWED_EXTENSIONS`).
- Corrupt/zero-page PDF → `INVALID_PDF` (gr.aзP resulting from `document_processor`).
- Image quality service (`app/services/image_quality.py`) rejects with
  `IMAGE_UNREADABLE` (blank/black), `DOCUMENT_NOT_DETECTED` (no ink),
  `IMAGE_CUTOFF` (border-ink heuristic).
- Everything else is "not an invoice" at LLM time → `NOT_AN_INVOICE`.

## 3. Field/type model (ケイセイ/型)

`app/schema/fast_rules_schema.yaml` + `app/schema/generic.py`
- Four persistent tuple blocks built at runtime as typed NamedTuples:
  SellerInfo, BuyerInfo (each name + address + tax id), Invoice (number, dates,
  currency, total, tax), Item (`Ord`, name, quantity, unit, unit price, line
  amount, notes — `rows_constant: n`, `ordinal_field: Ord`).
- Values remain strings (Kitsunex stores strings); *typing* lives in the
  NamedTuple annotations, and numeric fields are parsed per-field
  (`make_int`/`make_float`) in `schema/generic.py`.
- `Item.Ord` ↔ row correspondence: row index = ordinal, maintained in
  `app/pipeline/steps/resolution_stage.py::assemble_items`.

## 4. Resolution stage (ヨミホドキ/解決)

`app/services/resolvers.py`, `app/models/resolvers.py`
- `resolve(schema, data_header, ResolutionContext)` normalizes every field:
  amounts (¥1,234,567 円 → `1234567`) and dates (2024年4月1日 → `2024-04-01`)
  with fail-soft cleanup; names/addresses are whitespace/punctuation-collapsed.
- Failure modes: unresolved fields carry `ErrorSetting` (Kitsunex
  `Et.ErrorSetting`) instead of values; `CleanedValue.confidence` drives review.
- Reviewer override wins (`ResolutionContext.overrides`), same signature as the
  spec (`field → reviewer override`).
- Provider prefill (`@ERTY` / field from account) is represented by
  `is_prefill=True` which raises confidence to 0.9 (aspirational: filed per-file
  review below).

## 5. Strict validation (キョウセイ/DTO検証)

`app/services/validators.py`, `app/pipeline/steps/validation_stage.py`
- `strict_DTO_validator(schema, resolution)` marks CRITICAL violations for each
  `strict_required` field (SellerName, BuyerName, InvoiceNumber, TotalAmount)
  that is missing or unresolved, added to `condition_field_required`
  (InvoiceNumber) with the same severity.
- Rejected output still returns the extracted/final invoice data plus the
  violations as `InputError`s so the recovery flow can use them.

## 6. After conditions (アイゴウジョウケン/ambiguity)

- Pre-conditions (`field_for('Invoice.InvoiceNumber') is not None`) guard the
  extraction entry (`app/schema/fast_rules.py`).
- Post-condition `aggregate_total_cross_check()` compares the reported total
  against the summed line items (tolerance 2%). On mismatch the value is kept
  and a conflict anomaly is emitted
  (`app/pipeline/steps/resolution_stage.py::assemble_items`,
  `app/services/duplicate_conflict.py`).
- `condition_field_required` (only `Invoice.InvoiceNumber`) is checked via
  strict validation; the "minus suffix" marker behavior is acknowledged (Kitsunex
  legacy) but not applied verbatim — the prototype keeps uniqueness at the
  invoice store instead (see duplicates section).

## 7. Duplicate protection (ジュウフク/重複)

`app/services/duplicate_conflict.py`, `InvoiceStore` (`app/services/storage.py`)
- Natural key: `Invoice.InvoiceNumber`. On match with a stored invoice the job
  returns `duplicate: true`, `FoundDuplicate` with note/reason, and the
  `latest/1912` rule is applied: the newly-uploaded invoice is kept.
  - (Simulated shape accepted; enrichment and extras do not exist in our
    prototype, but the "form" of storing/adding new invoice + note is present.)

## 8. Vertical conflicts (タテムレ/縦積み)

`app/services/duplicate_conflict.py::_resolve_conflicts`
- All instances of a stored invoice number are collected ("all-instances"),
  fields that differ across instances become `ConflictAnomalySet`s
  (each with anomalies + unresolved flag) and are merged back into the body as
  `conflicts`. Values are never silently overwritten (`overwrite: false`) —
  they are surfaced for review.

## 9. Trust / confidence (シンライド/信頼)

`app/models/resolvers.py` (`CleanedValue.confidence`), `app/models/ocr.py`
- Banding per requirement: expected ≤0.7, likely ≤0.85, verified 0.95 (the
  bands exist as `oCgi threshold` constants but the classification into
  "highest/lower followers" is simplified): high-confidence duplicates autoskip;
  reviewer-verified values are auto-authored review → trusted (implemented as
  `verified` flag + `reprocess` overrides).

## 10. Etil-ccier (Hard typing / ハードタイピング)

`app/utils/typed.py` + `app/schema/generic.py`
- Typed output/Expected/Result NamedTuples are instantiated at runtime from the
  schema; `resolve_annotations()` evaluates forward-ref annotations against the
  captured module namespace. Values themselves remain strings (Kitsunex rule).

## Data persistence (We.K)

`app/utils/we.py`, `app/services/storage.py`
- `We_Requester` creates/finds the company and a file OID
  (`create_or_find_company`, `create_file`); `WH_Requester.requester` archives
  the processed file; every output row carries evidence refs
  `sf_oid|Block.Field` / `sf_oid|Item[i].Field` + OCR-image bounds for fields
  (`app/services/evidences.py`).
- Result artifacts: `{STORAGE_ROOT}/out/{job}/result.json` and `result.values`,
  plus a JSON invoice store (`invoices.json`) that powers the duplicate/conflict
  checks.

## Tests

`tests/` — 24 tests, all passing:
- schema shape + `parse_year`
- resolvers: money/date/name cleaning, overrides, missing-required errors
- similarity (n-grams) and extractor YAML parsing + primary/secondary merge
- pipeline: happy path (real generated PDF, faked LLM, deterministic OCR
  verdict), empty file, bad extension, corrupt PDF
- API roundtrip via `TestClient` (POST → jobs list → health)

## Honest caveats

1. OCR engines are optional/lazy: PaddleOCR and EasyOCR are imported only when
   an image/scan path actually runs OCR. Without either installed, scanned
   invoices produce `OCR_FAILED` (rejected with a clear message); text-layer
   PDFs work out of the box.
2. LLM is any OpenAI-compatible endpoint (Groq default). The prompt-engineered
   YAML extraction is the model of the spec's smart LLM stage, not a real
   long-context BAML/HXDo-style interposer.
3. "Provider prefill from account API" and multi-file per-file review mode are
   stubbed (query-param pass-through + override file) rather than connected to a
   live accounting API.
4. Duplicate/conflict logic runs against the local JSON invoice store; in
   production this is the We graph (which we do not ship).
5. The `MID_2000_prod_sim` / `latest/1912` two-letter legacy switches are
   represented as configuration flags in spirit; the always-on draft/sim
   behavior matches the demo requirements.