from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class InputErrorKind(str, Enum):
    EMPTY_FILE = "EMPTY_FILE"
    INVALID_FILETYPE = "INVALID_FILETYPE"
    INVALID_PDF = "INVALID_PDF"
    IMAGE_UNREADABLE = "IMAGE_UNREADABLE"
    DOCUMENT_NOT_DETECTED = "DOCUMENT_NOT_DETECTED"
    IMAGE_CUTOFF = "IMAGE_CUTOFF"
    OCR_FAILED = "OCR_FAILED"
    NOT_AN_INVOICE = "NOT_AN_INVOICE"
    VISION_FAILED = "VISION_FAILED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"
    DUPLICATE_CANDIDATE = "DUPLICATE_CANDIDATE"


class InputError(BaseModel):
    """Information about why an invoice was rejected or partially processed."""

    kind: InputErrorKind = InputErrorKind.INVALID_FILETYPE
    message: str = ""
    container_id: str = ""
    hints: list[str] = Field(default_factory=list)


class RuleViolation(BaseModel):
    """Result of the condition-validation / field-required checks."""

    field_name: str = ""
    message: str = ""
    severity: str = "CRITICAL"  # CRITICAL | WARNING