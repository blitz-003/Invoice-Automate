from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class OCRToken(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    confidence: float = 1.0
    bbox: list[float]  # [x, y, w, h] in the OCR-input image pixel space
    page: int = 1


class OCRResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    tokens: list[OCRToken] = []
    average_confidence: float = 0.0
    raw: Optional[dict] = None

    @property
    def token_count(self) -> int:
        return len(self.tokens)

    @property
    def text_chars(self) -> int:
        return len(self.text.strip())


class OCRValidationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reliable: bool = False
    confidence: float = 0.0
    reasons: list[str] = []
    garbage_ratio: float = 0.0
    anchor_hits: int = 0
    has_numbers: bool = False
    has_date_like: bool = False
    has_total_like: bool = False


class TextSpan(BaseModel):
    """A labeled span of text with an optional source region (used for evidence)."""

    model_config = ConfigDict(extra="ignore")

    text: str
    page: int = 1
    bbox: Optional[list[float]] = None  # [x, y, w, h] page-image pixel space

    @classmethod
    def from_token(cls, token: OCRToken) -> "TextSpan":
        return cls(text=token.text, page=token.page, bbox=token.bbox)