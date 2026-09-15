from __future__ import annotations

import re

from app.config import get_settings
from app.models.ocr import OCRResult, OCRValidationResult, OCRToken

INVOICE_ANCHORS = [
    "請求書", "御請求書", "請求書番号", "発行日", "お支払期日", "支払期日",
    "品名", "摘要", "数量", "単位", "単価", "金額", "小計", "消費税",
    "税率", "合計", "御請求金額", "登録番号", "請求金額",
]

_JAPANESE_RE = re.compile(
    r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\u3000-\u303f\u31f0-\u31ff\uff66-\uff9f]"
)
_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")
_DATE_RE = re.compile(r"(19|20)\d{2}[年/.-]\d{1,2}[月/.-]\d{1,2}")


class OCRValidator:
    """Deterministically decides whether OCR/PDF text is good enough for text LLM."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def validate(self, result: OCRResult) -> OCRValidationResult:
        settings = self.settings
        text = result.text
        tokens = result.tokens

        text_chars = len(text.replace("\n", "").strip())
        garbage_ratio = self._garbage_ratio(tokens) if tokens else self._garbage_ratio_text(text)

        anchor_hits = sum(1 for a in INVOICE_ANCHORS if a in text)
        has_numbers = bool(_NUMBER_RE.search(text))
        has_date_like = bool(_DATE_RE.search(text))
        has_total_like = bool(re.search(r"(合計|御請求金額|請求金額|総計)", text) and _NUMBER_RE.search(text))

        reasons: list[str] = []
        if result.average_confidence < settings.ocr_confidence_threshold:
            reasons.append("LOW_OCR_CONFIDENCE")
        if text_chars < settings.ocr_min_text_chars:
            reasons.append("TOO_LITTLE_TEXT")
        if garbage_ratio > settings.ocr_garbage_ratio_threshold:
            reasons.append("HIGH_GARBAGE_RATIO")
        if anchor_hits < settings.ocr_anchor_required:
            reasons.append("INVOICE_ANCHORS_MISSING")

        # A document that is clearly an invoice must have numbers.
        if not has_numbers:
            reasons.append("NO_NUMBERS")

        reliable = (
            result.average_confidence >= settings.ocr_confidence_threshold
            and text_chars >= settings.ocr_min_text_chars
            and garbage_ratio <= settings.ocr_garbage_ratio_threshold
            and anchor_hits >= settings.ocr_anchor_required
            and has_numbers
        )

        return OCRValidationResult(
            reliable=reliable,
            confidence=result.average_confidence,
            reasons=reasons,
            garbage_ratio=garbage_ratio,
            anchor_hits=anchor_hits,
            has_numbers=has_numbers,
            has_date_like=has_date_like,
            has_total_like=has_total_like,
        )

    @staticmethod
    def _garbage_ratio_text(text: str) -> float:
        if not text:
            return 1.0
        total = sum(1 for ch in text if not ch.isspace())
        if total == 0:
            return 1.0
        ok = sum(
            1 for ch in text
            if not ch.isspace()
            and (_JAPANESE_RE.match(ch) or ch.isalnum() or ch in "¥￥,./-：:；;，。・％%（）()[]")
        )
        return 1.0 - ok / total

    @staticmethod
    def _garbage_ratio(tokens: list[OCRToken]) -> float:
        if not tokens:
            return 1.0
        total = 0
        ok = 0
        for token in tokens:
            for ch in token.text:
                if ch.isspace():
                    continue
                total += 1
                if _JAPANESE_RE.match(ch) or ch.isalnum() or ch in "¥￥,./-：:；;，。・％%（）()[]":
                    ok += 1
        if total == 0:
            return 1.0
        return 1.0 - ok / total