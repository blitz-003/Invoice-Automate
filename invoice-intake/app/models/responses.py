from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ResolvedField(BaseModel):
    """A single resolved template field ready for persistence/output."""

    name: str
    value: str
    confidence: float
    verified: bool = False
    conflict: bool = False
    error: Optional[str] = None


class OutputRow(BaseModel):
    """One data row for the response (seller buyer rows, item rows, amount rows)."""

    key: str
    fields: dict[str, str] = Field(default_factory=dict)
    refs: dict[str, str] = Field(default_factory=dict)


class FinalInvoice(BaseModel):
    """Final resolved representation of a single invoice."""

    job_key: str
    source_id: str
    duplicate: bool = False
    metadata_review: bool = False
    reviewers: list[str] = Field(default_factory=list)
    resolved_fields: list[ResolvedField] = Field(default_factory=list)
    output_rows: list[OutputRow] = Field(default_factory=list)
    sanitized_values: dict[str, str] = Field(default_factory=dict)
    all_instances: dict[str, Any] = Field(default_factory=dict)
    external_ids: dict[str, str] = Field(default_factory=dict)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


class ApiRunResponse(BaseModel):
    job_key: str
    success: bool = True
    duplicate: bool = False
    metadata_review: bool = False
    invoice: Optional[FinalInvoice] = None
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    log: list[str] = Field(default_factory=list)