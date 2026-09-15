from __future__ import annotations

from dataclasses import dataclass

# Bands per the requirements: expected <= 0.7, likely <= 0.85, verified 0.95.
BAND_EXPECTED_UPPER = 0.70
BAND_LIKELY_UPPER = 0.85
BAND_VERIFIED = 0.95


@dataclass(frozen=True)
class ConfidenceScore:
    score: float
    band: str  # "low" | "expected" | "likely" | "verified"

    @property
    def needs_review(self) -> bool:
        return self.band in ("low", "expected")


def classify_confidence(score: float) -> str:
    if score is None:
        return "low"
    if score >= BAND_VERIFIED:
        return "verified"
    if score > BAND_LIKELY_UPPER:
        return "likely"
    if score > BAND_EXPECTED_UPPER:
        return "expected"
    return "low"


def score_confidence(field_confidences: list[float] | None) -> ConfidenceScore:
    values = [c for c in (field_confidences or []) if c is not None]
    if not values:
        return ConfidenceScore(0.0, "low")
    avg = sum(values) / len(values)
    return ConfidenceScore(round(avg, 3), classify_confidence(avg))