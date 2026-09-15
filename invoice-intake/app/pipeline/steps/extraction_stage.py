from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.models.input_errors import InputError, InputErrorKind
from app.models.ocr import OCRResult, OCRToken
from app.models.responses import ApiRunResponse
from app.schema.fast_rules import FastRulesTemplate
from app.services.document_processor import ProcessedDocument
from app.services.extractor import ExtractedData
from app.services.extractors import TextExtractor
from app.services.image_quality import ImageQualityService
from app.services.llm_clients import LLMClient
from app.services.ocr_service import OCRService
from app.services.preprocessor import ImagePreprocessor


def ocr_and_quality(
    processed: ProcessedDocument,
    log: list[str],
) -> tuple[Optional[OCRResult], bool, list[InputError]]:
    """OCR the document, or reuse the PDF text layer when it is usable."""
    errors: list[InputError] = []
    if processed.kind == "pdf_text":
        tokens: list[OCRToken] = []
        for page in processed.pages:
            for span in page.spans:
                tokens.append(OCRToken(
                    text=span.text,
                    confidence=1.0,
                    bbox=list(span.bbox),
                    page=span.page,
                ))
        result = OCRResult(
            text="\n".join(t.text for t in tokens),
            tokens=tokens,
            average_confidence=1.0 if tokens else 0.0,
        )
        log.append(f"ocr: using PDF text layer ({len(tokens)} spans)")
        return result, True, []

    settings = get_settings()
    image_path = processed.pages[0].image_path
    quality = ImageQualityService().assess(str(image_path))
    if not quality.acceptable:
        errors.append(InputError(
            kind=InputErrorKind[quality.reject_code] if quality.reject_code in InputErrorKind.__members__ else InputErrorKind.IMAGE_UNREADABLE,
            message=quality.reject_message or "The image could not be processed.",
        ))
        return None, False, errors

    ocr_path = str(image_path)
    if quality.needs_preprocessing:
        pre = ImagePreprocessor().preprocess(
            str(image_path), quality,
            str(Path(image_path).parent),
        )
        if pre != str(image_path):
            log.append("preprocess: sharpened/contrast/deskew applied")
            ocr_path = pre

    try:
        result = OCRService.shared().extract(ocr_path)
    except Exception as exc:  # pragma: no cover - engine failures
        errors.append(InputError(kind=InputErrorKind.OCR_FAILED,
                                 message=f"OCR engine failed: {exc}"))
        return None, False, errors
    log.append(f"ocr: engine={settings.ocr_engine} · tokens={len(result.tokens)} · confidence={result.average_confidence:.2f}")
    return result, False, errors


def extract(
    schema: FastRulesTemplate,
    processed: ProcessedDocument,
    ocr_result: Optional[OCRResult],
    text_mode: bool,
    log: list[str],
    response: ApiRunResponse,
) -> tuple[ExtractedData, Optional[ExtractedData], list[InputError], bool]:
    """Always extract via the text LLM from the OCR output (text + positions)."""
    llm = LLMClient()
    errors: list[InputError] = []

    if text_mode and processed.full_text:
        document_text = processed.full_text
    elif ocr_result and ocr_result.text:
        document_text = _format_ocr_with_positions(ocr_result, processed)
        log.append(
            f"llm: sending OCR text with positions (tokens={len(ocr_result.tokens)}, "
            f"chars={len(document_text)})"
        )
    else:
        document_text = ""

    data, data_err = TextExtractor(llm, schema).extract(document_text)
    errors += data_err
    _persist_raw_output(response.job_key, data)
    log.append(f"llm: raw output captured ({len(data.raw)} chars)")
    if llm.last_error:
        log.append(f"llm: text call error: {llm.last_error}")
    return data, None, errors, bool(data.header or data.items)


def _persist_raw_output(job_key: str, data) -> None:
    if not data.raw:
        return
    try:
        dest = Path(get_settings().storage_root) / "in" / job_key / "llm_raw.txt"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(data.raw, encoding="utf-8")
    except OSError:
        pass


def _format_ocr_with_positions(
    ocr_result: OCRResult, processed: ProcessedDocument,
) -> str:
    """Render OCR tokens in reading order, each annotated with its (x, y) box."""
    dims = {p.page_number: p for p in processed.pages}
    tokens = sorted(ocr_result.tokens, key=lambda t: (t.page, t.bbox[1], t.bbox[0]))
    lines: list[str] = []
    current_page: Optional[int] = None
    for token in tokens:
        if token.page != current_page:
            lines.append(f"[Page {token.page}]")
            current_page = token.page
        page = dims.get(token.page)
        if page and page.image_width and page.image_height:
            x = token.bbox[0] / page.image_width
            y = token.bbox[1] / page.image_height
            lines.append(f"({x:.3f}, {y:.3f}) {token.text}")
        else:
            lines.append(f"({token.bbox[0]}, {token.bbox[1]}) {token.text}")
    return "\n".join(lines)