from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.input_errors import InputError


class ErrorSetting(BaseModel):
    """Describes why a single field could not be resolved (Kitsunex Et.ErrorSetting)."""

    err_code: str = ""
    message: str = ""
    field_name: str = ""


class CleanedValue(BaseModel):
    """Output of the field-cleaning/normalization logic."""

    is_resolved: bool = False
    field_name: str = ""
    value: str = ""
    confidence: float = 0.5
    verified: bool = False
    is_number: bool = False
    numeric_value: float = 0.0
    note: str = ""
    error: Optional[ErrorSetting] = None

    @classmethod
    def resolved(
        cls,
        field_name: str,
        value: str,
        *,
        confidence: float = 0.5,
        is_number: bool = False,
        numeric_value: float = 0.0,
        note: str = "",
    ) -> "CleanedValue":
        return cls(
            is_resolved=True,
            field_name=field_name,
            value=value,
            confidence=confidence,
            is_number=is_number,
            numeric_value=numeric_value,
            note=note,
        )

    @classmethod
    def unresolved(cls, field_name: str, err_code: str, message: str) -> "CleanedValue":
        return cls(
            is_resolved=False,
            field_name=field_name,
            error=ErrorSetting(err_code=err_code, message=message, field_name=field_name),
        )


class ResolutionContext(BaseModel):
    """Context for resolving template fields from an extraction."""

    input_values: dict[str, str] = Field(default_factory=dict)
    overrides: dict[str, str] = Field(default_factory=dict)
    allows_empty: bool = False
    is_prefill: bool = False
    company_name: str = ""


class ResolutionResult(BaseModel):
    cleaned: dict[str, CleanedValue] = Field(default_factory=dict)
    errors: list[InputError] = Field(default_factory=list)