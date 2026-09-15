from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.models.job import JobStatus
from app.repositories.database import db_session


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobRepository:
    def create(self, file_name: str, file_hash: str, original_path: str) -> str:
        job_id = str(uuid.uuid4())
        now = _now()
        with db_session() as conn:
            conn.execute(
                "INSERT INTO jobs (id, file_name, file_hash, original_path, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, file_name, file_hash, original_path, JobStatus.RECEIVED.value, now, now),
            )
        return job_id

    def get(self, job_id: str) -> Optional[dict]:
        with db_session() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def find_by_hash(self, file_hash: str) -> Optional[dict]:
        with db_session() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE file_hash = ?", (file_hash,)).fetchone()
        return dict(row) if row else None

    def list_recent(self, limit: int = 50) -> list[dict]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, job_id: str) -> None:
        self.delete_invoice_data(job_id)
        with db_session() as conn:
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    def delete_invoice_data(self, job_id: str) -> None:
        with db_session() as conn:
            conn.execute(
                "DELETE FROM invoice_lines "
                "WHERE invoice_id IN (SELECT id FROM invoices WHERE job_id = ?)",
                (job_id,),
            )
            conn.execute(
                "DELETE FROM review_items "
                "WHERE invoice_id IN (SELECT id FROM invoices WHERE job_id = ?)",
                (job_id,),
            )
            conn.execute(
                "DELETE FROM audit_logs "
                "WHERE invoice_id IN (SELECT id FROM invoices WHERE job_id = ?)",
                (job_id,),
            )
            conn.execute("DELETE FROM invoices WHERE job_id = ?", (job_id,))

    def update_status(self, job_id: str, status: JobStatus, **extra) -> None:
        fields = ["status = ?"]
        values: list = [status.value]
        allowed = {"error_code", "error_message", "extraction_mode", "ocr_confidence", "confidence"}
        for key, val in extra.items():
            if key in allowed:
                fields.append(f"{key} = ?")
                values.append(val)
        values.append(_now())
        values.append(job_id)
        with db_session() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(fields)}, updated_at = ? WHERE id = ?", values)

    def increment_retry(self, job_id: str) -> None:
        with db_session() as conn:
            conn.execute("UPDATE jobs SET retry_count = retry_count + 1, updated_at = ? WHERE id = ?", (_now(), job_id))


class InvoiceRepository:
    def create(self, invoice_id: str, job_id: str, status: str, extracted: Optional[dict] = None,
               invoice_data: Optional[dict] = None, **kw) -> None:
        extracted_json = json.dumps(extracted, ensure_ascii=False) if extracted is not None else None
        data = invoice_data or {}
        now = _now()
        with db_session() as conn:
            conn.execute(
                "INSERT INTO invoices (id, job_id, partner_code, supplier_name, invoice_number, issue_date, due_date, "
                "currency, subtotal, tax_amount, total_amount, confidence, status, accounting_id, extraction_mode, "
                "ocr_confidence, extracted_json, evidence_json, reason_codes, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    invoice_id, job_id,
                    data.get("partner_code"), data.get("supplier_name"), data.get("invoice_number"),
                    data.get("issue_date"), data.get("due_date"), data.get("currency"),
                    data.get("subtotal"), data.get("tax_amount"), data.get("total_amount"),
                    kw.get("confidence"), status, kw.get("accounting_id"), kw.get("extraction_mode"),
                    kw.get("ocr_confidence"), extracted_json, kw.get("evidence_json"), kw.get("reason_codes"),
                    now, now,
                ),
            )
            if invoice_data and invoice_data.get("lines"):
                for pos, line in enumerate(invoice_data["lines"]):
                    conn.execute(
                        "INSERT INTO invoice_lines (invoice_id, position, description, quantity, unit, unit_price, amount, tax_code) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (invoice_id, pos, line.get("description"), line.get("quantity"),
                         line.get("unit"), line.get("unit_price"), line.get("amount"), line.get("tax_code")),
                    )

    def get(self, invoice_id: str) -> Optional[dict]:
        with db_session() as conn:
            row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        return dict(row) if row else None

    def get_lines(self, invoice_id: str) -> list[dict]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY position", (invoice_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def list_by_status(self, status: str, limit: int = 200) -> list[dict]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM invoices WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def list_recent(self, limit: int = 20) -> list[dict]:
        with db_session() as conn:
            rows = conn.execute("SELECT * FROM invoices ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def delete(self, invoice_id: str) -> None:
        with db_session() as conn:
            conn.execute("DELETE FROM invoice_lines WHERE invoice_id = ?", (invoice_id,))
            conn.execute("DELETE FROM review_items WHERE invoice_id = ?", (invoice_id,))
            conn.execute("DELETE FROM audit_logs WHERE invoice_id = ?", (invoice_id,))
            conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))

    def find_by_business_key(self, partner_code: str, invoice_number: str) -> Optional[dict]:
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM invoices WHERE partner_code = ? AND invoice_number = ? AND status = 'REGISTERED'",
                (partner_code, invoice_number),
            ).fetchone()
        return dict(row) if row else None

    def count_by_status(self) -> dict[str, int]:
        with db_session() as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS c FROM invoices GROUP BY status").fetchall()
        return {r["status"]: r["c"] for r in rows}

    def update_invoice(self, invoice_id: str, **fields) -> None:
        allowed = {"partner_code", "supplier_name", "invoice_number", "issue_date", "due_date",
                   "subtotal", "tax_amount", "total_amount", "confidence", "status",
                   "accounting_id", "reason_codes", "evidence_json"}
        cols, values = [], []
        for key, val in fields.items():
            if key in allowed:
                cols.append(f"{key} = ?")
                values.append(val)
        if not cols:
            return
        values.append(_now())
        values.append(invoice_id)
        with db_session() as conn:
            conn.execute(f"UPDATE invoices SET {', '.join(cols)}, updated_at = ? WHERE id = ?", values)

    def upsert_lines(self, invoice_id: str, lines: list[dict]) -> None:
        with db_session() as conn:
            conn.execute("DELETE FROM invoice_lines WHERE invoice_id = ?", (invoice_id,))
            for pos, line in enumerate(lines):
                conn.execute(
                    "INSERT INTO invoice_lines (invoice_id, position, description, quantity, unit, unit_price, amount, tax_code) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (invoice_id, pos, line.get("description"), line.get("quantity"), line.get("unit"),
                     line.get("unit_price"), line.get("amount"), line.get("tax_code")),
                )


class ReviewRepository:
    def create(self, invoice_id: str, reason_codes: list[str], confidence: float) -> int:
        now = _now()
        with db_session() as conn:
            cur = conn.execute(
                "INSERT INTO review_items (invoice_id, reason_codes, confidence, status, created_at) VALUES (?,?,?,?,?)",
                (invoice_id, json.dumps(reason_codes, ensure_ascii=False), confidence, "PENDING", now),
            )
            return cur.lastrowid

    def list_pending(self) -> list[dict]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM review_items WHERE status = 'PENDING' ORDER BY created_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_all(self, limit: int = 10_000) -> list[dict]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM review_items ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_for_invoice(self, invoice_id: str) -> Optional[dict]:
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM review_items WHERE invoice_id = ? ORDER BY id DESC LIMIT 1", (invoice_id,)
            ).fetchone()
        return dict(row) if row else None

    def resolve(self, review_id: int, status: str, reviewer: str | None, comment: str | None) -> None:
        now = _now()
        with db_session() as conn:
            conn.execute(
                "UPDATE review_items SET status = ?, reviewer = ?, comment = ?, resolved_at = ? WHERE id = ?",
                (status, reviewer, comment, now, review_id),
            )


class AuditRepository:
    def add(self, invoice_id: str, field_name: str, old_value, new_value,
            actor: str | None = None, reason: str | None = None) -> None:
        now = _now()
        with db_session() as conn:
            conn.execute(
                "INSERT INTO audit_logs (invoice_id, field_name, old_value, new_value, actor, reason, timestamp) "
                "VALUES (?,?,?,?,?,?,?)",
                (invoice_id, field_name, str(old_value) if old_value is not None else None,
                 str(new_value) if new_value is not None else None, actor, reason, now),
            )

    def list_for_invoice(self, invoice_id: str) -> list[dict]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE invoice_id = ? ORDER BY id ASC", (invoice_id,)
            ).fetchall()
        return [dict(r) for r in rows]