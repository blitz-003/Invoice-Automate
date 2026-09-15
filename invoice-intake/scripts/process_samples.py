"""Process every real sample in ../take-home/invoices and write a verdict report.

Usage:
    python scripts/process_samples.py                 # process all 12 samples
    python scripts/process_samples.py --limit 3       # first 3
    python scripts/process_samples.py --only invoice_01.pdf
    python scripts/process_samples.py --reset         # clear SQLite + accounting store first

Writes:
    reports/samples_report.json    machine-readable verdicts
    reports/samples_report.md      human-readable report
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.clients.accounting_client import AccountingClient, AccountingAPIError
from app.processing.processor import InvoiceProcessor, ProcessSummary
from app.repositories.database import init_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = PROJECT_ROOT.parent / "take-home" / "invoices"


def _parse_args(argv: list[str]) -> dict:
    out = {"limit": None, "only": None, "reset": False, "verify": False}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--limit":
            out["limit"] = int(argv[i + 1]); i += 2
        elif arg == "--only":
            out["only"] = argv[i + 1]; i += 2
        elif arg == "--reset":
            out["reset"] = True; i += 1
        elif arg == "--verify":
            out["verify"] = True; i += 1
        else:
            i += 1
    return out


def reset_state() -> None:
    db = PROJECT_ROOT / "data" / "invoice.db"
    if db.exists():
        db.unlink()
    init_db()
    try:
        removed = AccountingClient().delete_invoices()
        print(f"  reset: removed {removed} invoices from accounting mock")
    except (AccountingAPIError, Exception):
        print("  reset: accounting mock unreachable (start it with:")
        print("          python -m app.api.accounting_api")


def run(args: dict) -> list[dict]:
    files = sorted(p for p in SAMPLES_DIR.iterdir() if p.is_file()
                   and p.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png"})
    if args["only"]:
        files = [f for f in files if f.name == args["only"]]
        if not files:
            print(f"  no sample matches '{args['only']}'"); sys.exit(2)
    if args["limit"]:
        files = files[: args["limit"]]

    processor = InvoiceProcessor()
    results = []
    for path in files:
        summary = processor.process_file(str(path), file_name=path.name)
        results.append(_row(path.name, summary))
        _print_row(results[-1])
    return results


def _row(name: str, s: ProcessSummary) -> dict:
    inv = s.invoice or {}
    return {
        "file": name,
        "success": s.success,
        "status": s.status,
        "duplicate": s.duplicate,
        "original_job_id": s.original_job_id,
        "reason_codes": s.reason_codes,
        "errors": [e.get("message") for e in s.errors],
        "job_id": s.job_id,
        "invoice_id": s.invoice_id,
        "accounting_id": s.accounting_id,
        "supplier": fields_value(inv, "SellerInfo.SellerName"),
        "invoice_number": fields_value(inv, "Invoice.InvoiceNumber"),
        "issue_date": fields_value(inv, "Invoice.IssueDate"),
        "total_amount": fields_value(inv, "Invoice.TotalAmount"),
        "invoice_lines": len(
            [r for r in (inv.get("output_rows") or []) if (r or {}).get("key", "").startswith("Item")]
        ),
    }


def fields_value(invoice: dict | None, name: str):
    if not invoice:
        return None
    for f in invoice.get("resolved_fields") or []:
        if f.get("name") == name:
            return f.get("value")
    return None


def _print_row(row: dict) -> None:
    mark = "OK " if row["success"] else "XX "
    print(f"  {mark}{row['file']:<16} -> {row['status']:<14} "
          f"supplier={row['supplier']!r} inv={row['invoice_number']!r} "
          f"total={row['total_amount']!r} reasons={row['reason_codes']}")


def write_report(results: list[dict]) -> None:
    reports = PROJECT_ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    (reports / "samples_report.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "count": len(results), "samples": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Sample Processing Report", "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}  |  files: {len(results)}", "",
        "| file | status | success | duplicate | supplier | invoice# | issue date | total | lines | reasons | accounting_id |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['file']} | {r['status']} | {r['success']} | {r['duplicate']} "
            f"| {r['supplier']} | {r['invoice_number']} | {r['issue_date']} "
            f"| {r['total_amount']} | {r['invoice_lines']} | {','.join(r['reason_codes']) or '-'} | {r['accounting_id'] or '-'} |"
        )
    (reports / "samples_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nreport -> {reports / 'samples_report.md'}")


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    if args["reset"]:
        reset_state()
    results = run(args)
    write_report(results)
    if args["verify"]:
        from scripts.verify_golden import main as verify_main
        ve = [a for a in sys.argv[1:] if a != "--verify"]
        sys.exit(verify_main(ve))