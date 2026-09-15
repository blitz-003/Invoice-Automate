from __future__ import annotations

from fastapi import APIRouter

from app.clients.llm_client import LLMClient
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    settings = get_settings()
    models_available = LLMClient.models_available()
    return {
        "status": "ok",
        "engine": settings.ocr_engine,
        "llm_model": settings.llm_model,
        "vision_model": settings.vision_llm_model,
        "llm_configured": bool(settings.llm_api_key),
        "models_available": models_available,
        "storage_root": settings.storage_root,
    }