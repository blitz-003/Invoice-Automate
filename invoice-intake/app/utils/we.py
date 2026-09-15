from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger("we")


def kuma_platform_info() -> str:
    """Platform banner used in log dumps."""
    return "Kitsunex invoice-intake (We.K graph persistence)"


class WH_Requester:
    """Mimics the We.K WH_Requester integration layer (file registration)."""

    @staticmethod
    def requester(file_path: str) -> str:
        settings = get_settings()
        dest = Path(settings.we_wh_dir) / "_processed"
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / Path(file_path).name
        try:
            import shutil

            shutil.copy2(file_path, target)
        except OSError as exc:  # pragma: no cover
            logger.warning("wh copy failed: %s", exc)
        return str(target)


class We_Requester:
    """Mimics the We.K We_Requester layer (company + invoice source creation)."""

    def __init__(self, search_attributes: dict[str, str]):
        self.search_attributes = search_attributes

    def create_or_find_company(self, company_name: str) -> dict[str, str]:
        if not company_name:
            return {"oe:company_id": "", "oe:company_name": ""}
        return {
            "oe:company_id": _stable_id("company", company_name),
            "oe:company_name": company_name,
        }

    def create_file(self, job_key: str) -> str:
        return _stable_id("file", job_key)

    def requester(self, sf_id: str) -> dict[str, str]:
        return {
            "oe:sourcefile_oid": sf_id,
            "oe:sf_oid": sf_id,
            "oe:hash": _stable_id("hash", sf_id),
        }


def _stable_id(kind: str, value: str) -> str:
    import hashlib

    digest = hashlib.sha256(f"{kind}:{value}".encode("utf-8")).hexdigest()[:16]
    return f"{kind}-{digest}"