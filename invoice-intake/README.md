# Invoice Intake

A Kitsunex-style Japanese invoice intake service: upload a PDF / scanned photo,
the system OCRs it (Japanese), extracts fields with an LLM, resolves and
cross-checks them, detects duplicates/conflicts, and persists the result to a
We.K-like graph. Pure Python, FastAPI, no database required (JSON persistence).

## Quick start

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env        # set GROQ_API_KEY=...
python run.py                      # http://127.0.0.1:8000
```

- API docs: http://127.0.0.1:8000/docs
- Minimal UI: http://127.0.0.1:8000/ui
- Health check: `GET /health`
- Ingest: `POST /api/intake?field=1&uploadURL=...&fileName=...` with the file as multipart `file`.
- Job results: `GET /api/jobs`, `GET /api/jobs/{job_key}`
- Re-process with reviewer overrides: `POST /api/jobs/{job_key}/reprocess` with a JSON body of `{"Invoice.TotalAmount": "999"}`
  (override file lands in the job directory and is honored on the next run).

### Sample invoices

```powershell
python scripts/make_sample_invoices.py
```
Creates `samples/sample_1.pdf`, `samples/sample_2_duplicate.pdf`
(duplicate invoice number - triggers the duplicate/keep-new-invoice flow) and
`samples/sample_3_corrupt.pdf` (rejected with an `INVALID_PDF` error).
`sample_2` uses an ASCII text layer, so it runs without any OCR engine installed.

## Demo without an LLM key

`sample_*.pdf` are text-layer PDFs, so the pipeline uses their embedded text
(no OCR). If you have no `GROQ_API_KEY`, point `GROQ_BASE_URL` at a local
OpenAI-compatible server or edit `app/services/llm_clients.py`'s model name.

## OCR

- Default engine: [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) (`lang=japan`).
  Install with `pip install paddleocr` (first run downloads models).
- Fallback: `pip install easyocr` then set `OCR_ENGINE=easyocr`.
- OCR is lazy-imported; text-layer PDFs need neither engine.

## Pipeline overview

1. Preflight — file type / size, then PDF→page images (150 dpi) or image→PNG.
2. Text-layer detection — a PDF with ≥40 extractable characters is handled directly
   (OCR skipped); otherwise pages go through image-quality inspection
   (blank/black, cut-off, blur, contrast, skew) and preprocessing (unsharp mask,
   CLAHE, deskew, upscale).
3. Japanese OCR → `OCRResult` (tokens + confidence + bboxes).
4. OCR validation — confidence, garbage ratio, invoice anchor keywords
   (請求書/合計/…), presence of numbers decide whether text extraction is trusted.
5. LLM extraction — a `fast_rules_schema.yaml`-driven prompt yields YAML with
   header fields plus `Item[n].*` line items (typed NamedTuples built at runtime).
   Unreliable OCR/flat photos fall back to a vision LLM, and both stages are
   merged (text primary, vision fills gaps; line items aligned by ordinal/name).
6. Resolution — per-field cleaning (¥1,234,567 → `1234567`, dates → ISO),
   reviewer overrides win, unresolved required fields become strict-DTO violations.
7. Cross-checks — aggregate line total vs reported total; duplicates by natural
   key (invoice number) are flagged and the new invoice is kept; conflicting
   values across stored instances become conflict anomalies for review.
8. Assembly & persistence — resolved fields, output rows with We evidence refs
   (`sf_oid|Block.Field`), sanitized values, `result.json`/`result.values` drafts
   under `{STORAGE_ROOT}/out/{job}`, and a JSON invoice store.

## Configuration

See `app/config.py` (env-file friendly). Key settings:

| Env var                    | Meaning                                    |
|----------------------------|---------------------------------------------|
| `GROQ_API_KEY`             | LLM API key (OpenAI-compatible)             |
| `GROQ_BASE_URL`            | LLM endpoint                                |
| `TEXT_LLM_MODEL`           | model used for extraction                   |
| `OCR_ENGINE`               | `paddle` (default) or `easyocr`             |
| `STORAGE_ROOT`             | artifacts root (`data/in`, `data/out`)      |
| `ALLOWED_EXTENSIONS`       | `.pdf,.jpg,.jpeg,.png`                      |
| `MD_2000_prod_sim`         | unused (always-on draft/prod simulation)    |

## Tests

```powershell
python -m pytest tests -q
```

The suite generates real PDFs, fakes the LLM, monkeypatches OCR validation to a
deterministic verdict, and asserts end-to-end behavior: successful ingestion,
empty-file / bad-extension / corrupt-PDF rejection, YAML parsing, field
cleaning, n-gram similarity, and stage merging.

## Layout

```
app/
  config.py            settings
  main.py              FastAPI app
  models/              pydantic DTOs (input errors, outputs, resolution)
  pipeline/            run_pipeline orchestrator + step modules
  routers/             /api/intake, /api/jobs, /health
  schema/              rules template + dynamic typed-tuple generation
  services/            OCR, quality, extraction, resolvers, dedupe, storage…
  utils/               logging, We.K requester stubs, tuple helpers
config/fast_rules_schema.yaml
web/index.html         minimal upload UI
scripts/               sample generation + demo/test runners
tests/                 pytest suite
```