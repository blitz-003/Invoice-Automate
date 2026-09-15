from __future__ import annotations

import json
import threading
from pathlib import Path

from app.config import get_settings

_lock = threading.Lock()


class InvoiceStore:
    """Idempotent JSON persistence of processed invoices (We.K source-of-truth stand-in)."""

    def __init__(self, db_path: str | None = None):
        settings = get_settings()
        self.db_path = Path(db_path or settings.storage_root) / "invoices.json"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            self.db_path.write_text("[]", encoding="utf-8")

    def _read(self) -> list[dict]:
        with _lock:
            try:
                return json.loads(self.db_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return []

    def _write(self, records: list[dict]) -> None:
        with _lock:
            tmp = self.db_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.db_path)

    def list_invoices(self) -> list[dict]:
        return self._read()

    def has_invoice_number(self, number: str) -> bool:
        return any(r.get("Invoice.InvoiceNumber") == number for r in self._read() if number)

    def save_invoice(self, record: dict) -> None:
        records = self._read()
        key = record.get("job_key")
        records = [r for r in records if r.get("job_key") != key]
        records.append(record)
        self._write(records)


class JobManifest:
    """Per-job artifact bookkeeping stored under the artifacts root."""

    def __init__(self, job_key: str):
        settings = get_settings()
        self.job_dir = Path(settings.storage_root) / "in" / job_key
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.job_dir / "manifest.json"
        self._manifest = self._load()

    def _load(self) -> dict:
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {"job_key": self.job_dir.name}

    def set(self, key: str, value) -> None:
        self._manifest[key] = value
        self._save()

    def get(self, key: str, default=None):
        return self._manifest.get(key, default)

    def _save(self) -> None:
        self.manifest_path.write_text(
            json.dumps(self._manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @property
    def job_dir_path(self) -> Path:
        return self.job_dir