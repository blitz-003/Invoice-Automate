from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from app.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id             TEXT PRIMARY KEY,
    file_name      TEXT NOT NULL,
    file_hash      TEXT NOT NULL,
    original_path  TEXT NOT NULL,
    status         TEXT NOT NULL,
    error_code     TEXT,
    error_message  TEXT,
    extraction_mode TEXT,
    ocr_confidence REAL,
    confidence     REAL,
    retry_count    INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    id            TEXT PRIMARY KEY,
    job_id        TEXT NOT NULL REFERENCES jobs(id),
    partner_code  TEXT,
    supplier_name TEXT,
    invoice_number TEXT,
    issue_date    TEXT,
    due_date      TEXT,
    currency      TEXT DEFAULT 'JPY',
    subtotal      INTEGER,
    tax_amount    INTEGER,
    total_amount  INTEGER,
    confidence    REAL,
    status        TEXT NOT NULL,
    accounting_id TEXT,
    extraction_mode TEXT,
    ocr_confidence REAL,
    extracted_json TEXT,
    evidence_json  TEXT,
    reason_codes   TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoice_lines (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    position   INTEGER NOT NULL,
    description TEXT NOT NULL,
    quantity    INTEGER,
    unit        TEXT,
    unit_price  INTEGER,
    amount      INTEGER NOT NULL,
    tax_code    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id   TEXT NOT NULL REFERENCES invoices(id),
    reason_codes TEXT NOT NULL,
    confidence   REAL,
    status       TEXT NOT NULL DEFAULT 'PENDING',
    reviewer     TEXT,
    comment      TEXT,
    created_at   TEXT NOT NULL,
    resolved_at  TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value  TEXT,
    new_value  TEXT,
    actor      TEXT,
    reason     TEXT,
    timestamp  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(file_hash);
CREATE UNIQUE INDEX IF NOT EXISTS ux_invoices_registered
    ON invoices(partner_code, invoice_number) WHERE status = 'REGISTERED';
CREATE INDEX IF NOT EXISTS idx_invoices_job ON invoices(job_id);
CREATE INDEX IF NOT EXISTS idx_review_status ON review_items(status);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    settings = get_settings()
    path = db_path or str(settings.db_path)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    settings = get_settings()
    if db_path is None:
        settings.ensure_dirs()
        db_path = str(settings.db_path)
    with get_connection(db_path) as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def db_session(db_path: str | None = None):
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()