from typing import Any, Optional

from pydantic import BaseModel, Field


class ConflictFieldOutcome(BaseModel):
    """One field value that was overridden because it conflicts with history."""

    field_name: str
    current_value: str = ""
    current_note: str = ""
    other_value: str = ""
    other_note: str = ""
    overwrite: bool = False


class FoundDuplicate(BaseModel):
    """A strong duplicate candidate — keep-new-invoice semantics are applied."""

    invoice_id: str = ""
    note: str = ""
    reason: str = ""


class ConflictAnomalySet(BaseModel):
    """One set of vertically-conflicting outputs and the reconciliation result."""

    field_name: str = ""
    anomalies: list[Any] = Field(default_factory=list)
    is_resolved: bool = False
    resolved_note: str = ""
    resolved_value: str = ""
    unresolved: Optional[str] = None