from __future__ import annotations

import threading

import numpy as np

from app.config import get_settings
from app.models.ocr import OCRResult, OCRToken

_lock = threading.Lock()
_shared: "OCRService | None" = None


class OCRService:
    """Japanese OCR. PaddleOCR by default with an EasyOCR fallback.

    Instances cache their engine; ``shared()`` returns a process-wide instance so
    the ~45s PaddleOCR model load happens once and every later image is
    inference-only. ``extract`` is serialized with a lock (Paddle inference is
    not thread-safe).
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self._paddle = None
        self._easy = None

    @classmethod
    def shared(cls) -> "OCRService":
        global _shared
        if _shared is None:
            with _lock:
                if _shared is None:
                    _shared = cls()
        return _shared

    def _get_paddle(self):
        if self._paddle is None:
            from paddleocr import PaddleOCR

            self._paddle = PaddleOCR(
                lang=self.settings.ocr_lang,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=True,
                enable_mkldnn=False,
            )
        return self._paddle

    def _get_easy(self):
        if self._easy is None:
            import easyocr

            self._easy = easyocr.Reader(["ja", "en"], gpu=False)
        return self._easy

    def extract(self, image_path: str) -> OCRResult:
        with _lock:
            if self.settings.ocr_engine == "easyocr":
                return self._extract_easyocr(image_path)
            try:
                return self._extract_paddle(image_path)
            except Exception:
                # Fall back to EasyOCR if the paddle path fails at runtime.
                try:
                    return self._extract_easyocr(image_path)
                except Exception:
                    raise

    def _extract_paddle(self, image_path: str) -> OCRResult:
        ocr = self._get_paddle()
        raw = ocr.predict(str(image_path))

        tokens: list[OCRToken] = []
        for page_index, page_result in enumerate(raw, start=1):
            texts = page_result.get("rec_texts") or []
            scores = page_result.get("rec_scores") or []
            polys = page_result.get("rec_polys") or []
            if not texts and not polys:
                texts = page_result.get("dt_texts") or []
                scores = page_result.get("dt_scores") or []
                polys = page_result.get("dt_polys") or []
            for text, score, poly in zip(texts, scores, polys):
                text = (text or "").strip()
                if not text:
                    continue
                poly = np.asarray(poly, dtype=np.float64)
                xs, ys = poly[:, 0], poly[:, 1]
                tokens.append(
                    OCRToken(
                        text=text,
                        confidence=float(score),
                        bbox=[round(float(xs.min()), 1), round(float(ys.min()), 1),
                              round(float(xs.max() - xs.min()), 1), round(float(ys.max() - ys.min()), 1)],
                        page=page_index,
                    )
                )
        return self._build_result(tokens)

    def _extract_easyocr(self, image_path: str) -> OCRResult:
        reader = self._get_easy()
        raw = reader.readtext(image_path)
        tokens: list[OCRToken] = []
        for page_index, result in enumerate([raw], start=1):
            for bbox, text, score in result:
                text = (text or "").strip()
                if not text:
                    continue
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                tokens.append(
                    OCRToken(
                        text=text,
                        confidence=float(score),
                        bbox=[round(min(xs), 1), round(min(ys), 1),
                              round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)],
                        page=page_index,
                    )
                )
        return self._build_result(tokens)

    @staticmethod
    def _build_result(tokens: list[OCRToken]) -> OCRResult:
        tokens.sort(key=lambda t: (t.page, t.bbox[1], t.bbox[0]))
        text = "\n".join(t.text for t in tokens)
        avg_conf = float(np.mean([t.confidence for t in tokens])) if tokens else 0.0
        return OCRResult(text=text, tokens=tokens, average_confidence=avg_conf)