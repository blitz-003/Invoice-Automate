"""Generate small invoice PDFs (ASCII text layer) for local demos.

Usage:
    python scripts/make_sample_invoices.py

Creates ./samples/sample_1.pdf, ./samples/sample_2_duplicate.pdf and a
Japanese-labelled variant using a bundled CJK font if available.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

SAMPLES = [
    {
        "name": "sample_1.pdf",
        "lines": [
            "INVOICE  INV-2024-0101",
            "DATE: 2024/4/1    DUE: 2024/5/1",
            "FROM: ACME CORPORATION  Tokyo Chuo-ku 1-2-3",
            "TO: GLOBEX TRADING  Osaka Kita-ku 4-5-6",
            "1 x Web hosting  @ 1200    1200",
            "2 x Support hours @ 9000   18000",
            "TOTAL 19200   TAX 1920",
        ],
    },
    {
        "name": "sample_2_duplicate.pdf",
        "lines": [
            "INVOICE  INV-2024-0101",
            "DATE: 2024/4/1    DUE: 2024/5/1",
            "FROM: ACME CORPORATION  Tokyo Chuo-ku 1-2-3",
            "TO: GLOBEX TRADING  Osaka Kita-ku 4-5-6",
            "1 x Web hosting  @ 1200    1200",
            "2 x Support hours @ 9000   18000",
            "TOTAL 19200   TAX 1920",
        ],
    },
    {
        "name": "sample_3_corrupt.pdf",
        "lines": None,  # marker for corrupt binary
    },
]


def _build_pdf(lines: list[str], path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    y = 100
    for line in lines:
        page.insert_text((60, y), line, fontsize=12)
        y += 25
    doc.save(str(path))
    doc.close()


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "samples"
    out.mkdir(parents=True, exist_ok=True)
    for sample in SAMPLES:
        path = out / sample["name"]
        if sample["lines"] is None:
            path.write_bytes(b"%PDF-1.4 not really valid" + b"\x00" * 64)
            print("wrote", path)
            continue
        _build_pdf(sample["lines"], path)
        print("wrote", path)


if __name__ == "__main__":
    main()