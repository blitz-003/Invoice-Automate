"""Build a raw text dump of the 12 sample invoices (PDF text layer or OCR)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ocr_service import OCRService

SAMPLES = Path(__file__).resolve().parent.parent.parent / "take-home" / "invoices"
OUT = Path(__file__).resolve().parent.parent.parent / "take-home" / "text_dump.json"


def pdf_text(path: Path) -> str:
    import pymupdf

    doc = pymupdf.open(str(path))
    return "\n".join(p.get_text() for p in doc)


def main() -> None:
    ocr = OCRService.shared()
    data: dict = {}
    for p in sorted(SAMPLES.iterdir()):
        if not p.is_file() or p.suffix.lower() not in {".pdf", ".jpg", ".jpeg", ".png"}:
            continue
        if p.suffix.lower() == ".pdf":
            text = pdf_text(p)
            if len(text.strip()) > 40:
                data[p.name] = {"source": "pdf_text", "text": text}
                continue
        data[p.name] = {"source": "ocr", "text": ocr.extract(str(p)).text}
        print(f"  {p.name}: {data[p.name]['source']}")
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({len(data)} files)")


if __name__ == "__main__":
    main()