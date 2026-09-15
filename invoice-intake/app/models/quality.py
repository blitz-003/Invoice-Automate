from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class ImageQualityResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    width: int = 0
    height: int = 0
    blur_score: float = 0.0
    contrast_score: float = 0.0
    skew_angle: float = 0.0
    darkness: float = 0.0

    document_detected: bool = True
    cutoff_detected: bool = False
    blank_or_black: bool = False

    acceptable: bool = True
    needs_preprocessing: bool = False

    reason: Optional[str] = None
    reject_code: str = ""
    reject_message: str = ""

    @classmethod
    def reject(cls, code: str, message: str) -> "ImageQualityResult":
        return cls(
            acceptable=False,
            document_detected=False,
            needs_preprocessing=False,
            reason=code,
            reject_code=code,
            reject_message=message,
        )