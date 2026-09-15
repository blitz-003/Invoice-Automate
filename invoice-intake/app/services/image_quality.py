from __future__ import annotations

import numpy as np

from app.config import get_settings
from app.models.quality import ImageQualityResult


class ImageQualityService:
    """Assesses whether an image is usable and whether preprocessing is needed."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    @staticmethod
    def _load_gray(image_path: str) -> np.ndarray:
        import cv2

        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError("image could not be loaded")
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        return gray

    @staticmethod
    def _skew_angle(gray: np.ndarray) -> float:
        import cv2

        height, width = gray.shape
        if width < 40 or height < 40:
            return 0.0
        edges = cv2.Canny(gray, 80, 180)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                minLineLength=max(40, int(width * 0.2)),
                                maxLineGap=8)
        if lines is None:
            return 0.0
        angles = []
        for line in lines.reshape(-1, 4):
            x1, y1, x2, y2 = line
            dx, dy = x2 - x1, y2 - y1
            if abs(dx) < 1e-6:
                continue
            angle = np.degrees(np.arctan(dy / dx))
            if abs(angle) < 45:  # near-horizontal lines
                angles.append(angle)
        if not angles:
            return 0.0
        median = float(np.median(angles))
        if abs(median) < 0.3:
            return 0.0
        return median

    def assess(self, image_path: str) -> ImageQualityResult:
        import cv2

        settings = self.settings
        gray = self._load_gray(image_path)
        height, width = gray.shape

        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        contrast_score = float(gray.std())
        mean = float(gray.mean()) / 255.0

        ink = (gray < 128)
        ink_ratio = float(ink.mean())

        # Border ring ink coverage (used as a conservative cutoff signal)
        ring = 10
        top = gray[:ring, :]; bottom = gray[-ring:, :]
        left = gray[:, :ring]; right = gray[:, -ring:]
        border_ink = float((np.concatenate([top.ravel(), bottom.ravel(), left.ravel(), right.ravel()]) < 128).mean())

        skew = self._skew_angle(gray)

        result = ImageQualityResult(
            width=width,
            height=height,
            blur_score=blur_score,
            contrast_score=contrast_score,
            skew_angle=skew,
            darkness=mean,
        )

        # Blank / black / white detection
        if ink_ratio < 0.001:
            if mean < 0.12:
                return ImageQualityResult.reject(
                    "IMAGE_UNREADABLE",
                    "The image is unreadable. Please upload a clearer image.",
                )
            return ImageQualityResult.reject(
                "DOCUMENT_NOT_DETECTED",
                "The uploaded image does not appear to contain an invoice.",
            )

        # Conservative cutoff heuristic: heavy ink right at the image border
        if border_ink > 0.85 and ink_ratio > 0.05:
            return ImageQualityResult.reject(
                "IMAGE_CUTOFF",
                "The invoice appears to be cut off. Please upload the complete document.",
            )

        resolution_ok = width >= settings.min_width and height >= settings.min_height
        blur_bad = blur_score < settings.blur_threshold
        contrast_bad = contrast_score < settings.min_contrast
        skew_bad = abs(skew) > settings.max_skew_degrees

        needs_preprocessing = blur_bad or contrast_bad or skew_bad or not resolution_ok
        return ImageQualityResult(
            width=width,
            height=height,
            blur_score=blur_score,
            contrast_score=contrast_score,
            skew_angle=skew,
            darkness=mean,
            document_detected=True,
            acceptable=True,
            needs_preprocessing=needs_preprocessing,
        )