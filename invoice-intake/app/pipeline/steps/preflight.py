from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.models.input_errors import InputError, InputErrorKind
from app.schema.fast_rules import FastRulesTemplate
from app.services.document_processor import DocumentProcessor, ProcessedDocument


@dataclass
class PreflightContext:
    source_file: Path
    job_key: str
    converted_image: Optional[str] = None
    text_path: Optional[str] = None
    notes: list[str] = field(default_factory=list)


def check(source_file: Path, schema: FastRulesTemplate, job_key: str) -> tuple[list[InputError], PreflightContext]:
    settings = get_settings()
    ctx = PreflightContext(source_file=source_file, job_key=job_key)
    ext = source_file.suffix.lower()
    if ext not in settings.allowed_ext_list:
        return [InputError(
            kind=InputErrorKind.INVALID_FILETYPE,
            message=f"Unsupported file type '{ext}'. Allowed: {settings.allowed_extensions}.",
        )], ctx
    size_mb = source_file.stat().st_size / (1024 * 1024)
    if size_mb > settings.max_file_size_mb:
        return [InputError(
            kind=InputErrorKind.INVALID_FILETYPE,
            message=f"File is {size_mb:.1f} MB; maximum allowed is {settings.max_file_size_mb} MB.",
        )], ctx
    return [], ctx


def process_pages(
    ctx: PreflightContext,
    schema: FastRulesTemplate,
    log: list[str],
) -> tuple[Optional[ProcessedDocument], list[InputError]]:
    settings = get_settings()
    pages_dir = Path(settings.storage_root) / "in" / ctx.job_key / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    processor = DocumentProcessor()
    try:
        doc = processor.process(str(ctx.source_file), str(pages_dir))
    except Exception as exc:
        return None, [InputError(
            kind=InputErrorKind.INVALID_PDF,
            message=f"The document could not be parsed: {exc}",
        )]
    if not doc.pages:
        return None, [InputError(
            kind=InputErrorKind.EMPTY_FILE,
            message="The document yielded no pages.",
        )]
    log.append(f"document: {doc.kind} · {doc.page_count} page(s) · text_usable={bool(doc.usable_text)}")
    return doc, []