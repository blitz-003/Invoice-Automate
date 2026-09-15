from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.config import get_settings


class FileValidationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    valid: bool
    error_code: Optional[str] = None
    message: Optional[str] = None
    extension: Optional[str] = None
    mime: Optional[str] = None

    @classmethod
    def reject(cls, code: str, message: str) -> "FileValidationResult":
        return cls(valid=False, error_code=code, message=message)


def _sniff_mime(path: Path) -> Optional[str]:
    with open(path, "rb") as fh:
        head = fh.read(16)
    if head[:4] == b"%PDF":
        return "application/pdf"
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if head[:4] == b"II*\x00" or head[:4] == b"MM\x00*":
        return "image/tiff"
    return None


def validate_file(file_path: str) -> FileValidationResult:
    settings = get_settings()
    path = Path(file_path)
    if not path.exists():
        return FileValidationResult.reject("EMPTY_FILE", "File does not exist.")
    if not path.is_file():
        return FileValidationResult.reject("EMPTY_FILE", "Path is not a file.")

    ext = path.suffix.lower()
    if ext not in settings.allowed_ext_list:
        return FileValidationResult.reject(
            "UNSUPPORTED_FILE_TYPE",
            f"Unsupported file type '{ext}'. Supported: {settings.allowed_extensions}",
        )

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > settings.max_file_size_mb:
        return FileValidationResult.reject(
            "FILE_TOO_LARGE",
            f"File is {size_mb:.1f} MB which exceeds the {settings.max_file_size_mb} MB limit",
        )
    if path.stat().st_size == 0:
        return FileValidationResult.reject("EMPTY_FILE", "File is empty.")

    mime = _sniff_mime(path)
    if mime is None:
        return FileValidationResult.reject(
            "CORRUPTED_FILE", "File content does not match a supported format."
        )

    if mime == "application/pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            if len(reader.pages or []) == 0:
                return FileValidationResult.reject(
                    "EMPTY_FILE", "PDF contains no pages."
                )
        except Exception as exc:
            return FileValidationResult.reject(
                "CORRUPTED_FILE", f"Could not read PDF: {exc}"
            )
        return FileValidationResult(valid=True, extension=ext, mime=mime)

    # Image validity
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as img:
            ImageOps.exif_transpose(img)
            img.load()
            if img.size[0] <= 0 or img.size[1] <= 0:
                raise ValueError("invalid image dimensions")
    except Exception as exc:
        return FileValidationResult.reject(
            "CORRUPTED_FILE", f"Could not read image: {exc}"
        )
    return FileValidationResult(valid=True, extension=ext, mime=mime)