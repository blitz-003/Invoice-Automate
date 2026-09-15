"""Delete all processed / uploaded data and generated reports.

Removes the SQLite tables' contents (jobs, invoices, lines, reviews, audit),
per-job artifacts under data/in, the invoices.json store file, uploads/ and
processed/, and any generated files in reports/.

Usage:
    .venv\\Scripts\\python scripts\\reset_data.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.repositories.database import get_connection


def main() -> None:
    settings = get_settings()
    counts: dict[str, int] = {}

    with get_connection() as conn:
        for table in ("audit_logs", "review_items", "invoice_lines", "invoices", "jobs"):
            cur = conn.execute(f"DELETE FROM {table}")
            counts[table] = cur.rowcount
        conn.execute(
            "DELETE FROM sqlite_sequence "
            "WHERE name IN ('audit_logs', 'review_items', 'invoice_lines')"
        )
        conn.commit()

    for sub in ("in", "out", "we_wh"):
        root = Path(settings.storage_root) / sub
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)

    store = Path(settings.storage_root) / "invoices.json"
    if store.exists():
        store.write_text("[]", encoding="utf-8")

    for attr in ("upload_dir", "processed_dir"):
        target = Path(getattr(settings, attr))
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)

    reports = Path("reports")
    removed = 0
    if reports.exists():
        for child in reports.iterdir():
            if child.is_file():
                child.unlink()
                removed += 1

    print("reset complete:", counts, f"(reports removed: {removed})")


if __name__ == "__main__":
    main()