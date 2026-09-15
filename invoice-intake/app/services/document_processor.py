from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.config import get_settings
from app.models.ocr import TextSpan


class ProcessedPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page_number: int
    image_path: Optional[str] = None
    image_width: int = 0
    image_height: int = 0
    spans: list[TextSpan] = []
    text: str = ""


class ProcessedDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: str  # 'pdf_text' | 'pdf_image' | 'image'
    pages: list[ProcessedPage]
    full_text: str = ""

    @property
    def usable_text(self) -> bool:
        return self.kind == "pdf_text"

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def text_for_page(self, page_index: int) -> str:
        return "\n".join(s.text for s in self.pages[page_index].spans)


_MIN_PDF_TEXT_CHARS = 40


class DocumentProcessor:
    """Converts a validated input file into page images and/or text spans."""

    def process(self, file_path: str, out_dir: str) -> ProcessedDocument:
        from PIL import Image, ImageOps

        path = Path(file_path)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        ext = path.suffix.lower()
        if ext == ".pdf":
            return self._process_pdf(path, out_dir)
        if ext in (".jpg", ".jpeg", ".png"):
            page = self._save_image_page(path, 1, out_dir)
            return ProcessedDocument(
                kind="image",
                pages=[page],
                full_text=page.text,
            )
        raise ValueError(f"unsupported file: {ext}")

    def _process_pdf(self, path: Path, out_dir: str) -> ProcessedDocument:
        import pymupdf  # PyMuPDF 1.28+ (fitz still aliased)

        settings = get_settings()
        zoom = settings.pdf_render_dpi / 72.0
        doc = pymupdf.open(path)
        pages: list[ProcessedPage] = []
        total_text_len = 0
        for idx, pdf_page in enumerate(doc, start=1):
            page_text, spans = self._pdf_page_spans(pdf_page, zoom)
            total_text_len += len(page_text)
            image_path, width, height = self._render_page(pdf_page, idx, out_dir)
            pages.append(
                ProcessedPage(
                    page_number=idx,
                    image_path=image_path,
                    image_width=width,
                    image_height=height,
                    spans=spans,
                    text=page_text,
                )
            )
        doc.close()

        has_text_layer = total_text_len >= _MIN_PDF_TEXT_CHARS
        kind = "pdf_text" if has_text_layer else "pdf_image"
        full_text = "\n".join(p.text for p in pages)
        return ProcessedDocument(kind=kind, pages=pages, full_text=full_text)

    @staticmethod
    def _pdf_page_spans(pdf_page, zoom: float) -> tuple[str, list[TextSpan]]:
        raw = pdf_page.get_text("dict")
        spans: list[TextSpan] = []
        for block in raw.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line.get("spans", [])).strip()
                if not text:
                    continue
                x0, y0, x1, y1 = line.get("bbox", (0, 0, 0, 0))
                spans.append(
                    TextSpan(
                        text=text,
                        page=pdf_page.number + 1,
                        bbox=[round(x0 * zoom, 1), round(y0 * zoom, 1),
                              round((x1 - x0) * zoom, 1), round((y1 - y0) * zoom, 1)],
                    )
                )
        full_text = "\n".join(s.text for s in spans)
        return full_text, spans

    @staticmethod
    def _render_page(pdf_page, page_number: int, out_dir: str) -> tuple[str, int, int]:
        from PIL import Image
        import pymupdf

        settings = get_settings()
        zoom = settings.pdf_render_dpi / 72.0
        pix = pdf_page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        image_path = str(Path(out_dir) / f"page_{page_number}.png")
        pix.save(image_path)
        with Image.open(image_path) as img:
            width, height = img.size
        return image_path, width, height

    @staticmethod
    def _save_image_page(path: Path, page_number: int, out_dir: str) -> ProcessedPage:
        from PIL import Image, ImageOps

        image_path = str(Path(out_dir) / f"page_{page_number}.png")
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            width, height = img.size
            img.save(image_path, format="PNG")
        return ProcessedPage(page_number=page_number, image_path=image_path,
                             image_width=width, image_height=height)

    @staticmethod
    def store_original(src_path: str, dest_dir: str, file_name: str = "") -> str:
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        dest = Path(dest_dir) / (file_name or Path(src_path).name)
        shutil.copy2(src_path, dest)
        return str(dest)