from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Accounting system (mock) ---
    accounting_api_url: str = "http://localhost:8080"
    accounting_api_key: str = "demo-key-1234"

    # --- LLM (Groq, OpenAI-compatible) ---
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    text_llm_model: str = "qwen/qwen3.8-27b"
    vision_llm_model: str = "qwen/qwen3.8-27b"
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 120.0
    llm_max_tokens: int = 8192
    vision_max_image_side: int = 1400
    vision_jpeg_quality: int = 85

    # --- OCR ---
    ocr_engine: str = "paddle"  # paddle | easyocr
    ocr_confidence_threshold: float = 0.70
    ocr_garbage_ratio_threshold: float = 0.30
    ocr_min_text_chars: int = 40
    ocr_anchor_required: int = 2
    ocr_lang: str = "japan"

    # --- Image quality ---
    min_width: int = 800
    min_height: int = 600
    blur_threshold: float = 60.0
    min_contrast: float = 20.0
    max_skew_degrees: float = 10.0
    min_document_area_ratio: float = 0.04

    # --- Pipeline / routing ---
    auto_approve_confidence: float = 0.90
    review_confidence: float = 0.70
    max_file_size_mb: int = 20
    pdf_render_dpi: int = 150
    allowed_extensions: str = ".pdf,.jpg,.jpeg,.png"
    max_review_retries: int = 3

    # --- Pipeline routing knobs ---
    vision_on_unreliable: bool = True
    vision_enabled: bool = True
    persist_drafts: bool = True

    # --- Storage ---
    database_url: str = "sqlite:///./data/invoice.db"
    upload_dir: str = "./uploads"
    processed_dir: str = "./processed"
    storage_root: str = "./data"
    we_wh_dir: str = "./data/we_wh"

    @property
    def llm_api_key(self) -> str:
        return self.groq_api_key

    @property
    def llm_base_url(self) -> str:
        return self.groq_base_url

    @property
    def llm_model(self) -> str:
        return self.text_llm_model

    @property
    def allowed_ext_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()]

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def db_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            rel = self.database_url[len("sqlite:///"):]
            p = Path(rel)
            if not p.is_absolute():
                p = self.project_root / p
            return p
        raise ValueError("Only sqlite URLs are supported in the prototype")

    def ensure_dirs(self) -> None:
        for key in ("upload_dir", "processed_dir"):
            Path(getattr(self, key)).mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()