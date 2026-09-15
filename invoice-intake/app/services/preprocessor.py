from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.models.quality import ImageQualityResult


class ImagePreprocessor:
    """Conditionally improves an image based on the quality assessment."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def preprocess(self, image_path: str, quality: ImageQualityResult, out_dir: str) -> str:
        import cv2
        import numpy as np

        Path(out_dir).mkdir(parents=True, exist_ok=True)
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("image could not be loaded for preprocessing")

        changed = False

        if quality.blur_score < self.settings.blur_threshold:
            gauss = cv2.GaussianBlur(img, (0, 0), 3.0)
            img = cv2.addWeighted(img, 1.5, gauss, -0.5, 0)  # unsharp mask
            img = cv2.fastNlMeansDenoisingColored(img, None, 6, 6, 7, 21)
            changed = True

        if quality.contrast_score < self.settings.min_contrast:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img = cv2.cvtColor(clahe.apply(gray), cv2.COLOR_GRAY2BGR)
            changed = True

        if abs(quality.skew_angle) > self.settings.max_skew_degrees:
            angle = quality.skew_angle
            h, w = img.shape[:2]
            center = (w / 2, h / 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            img = cv2.warpAffine(img, matrix, (w, h), borderValue=(255, 255, 255))
            changed = True

        if img.shape[1] < self.settings.min_width or img.shape[0] < self.settings.min_height:
            scale = max(self.settings.min_width / img.shape[1], self.settings.min_height / img.shape[0])
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            changed = True

        if not changed:
            return image_path

        out_path = str(Path(out_dir) / (Path(image_path).stem + "_processed.png"))
        cv2.imwrite(out_path, img)
        return out_path