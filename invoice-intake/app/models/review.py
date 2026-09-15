from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ReviewDecision(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReviewItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    invoice_id: str
    reason_codes: list[str] = []
    confidence: float = 0.0
    status: ReviewDecision = ReviewDecision.PENDING
    reviewer: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class AuditLog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    invoice_id: str
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    actor: Optional[str] = None
    reason: Optional[str] = None
    timestamp: datetime


class ProcessingError(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    message: str
    stage: str
    details: Optional[dict] = None
    retryable: bool = False