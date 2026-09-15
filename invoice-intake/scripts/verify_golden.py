"""Verify the pipeline against the hand-built golden dataset.

End-to-end check: reprocesses every sample in a throwaway sandbox database
(so file dedup/db state never interferes) and compares the extracted +
resolved fields against ``take-home/golden.json``.

Usage:
    python scripts/verify_golden.py                       # all 12 files (fresh sandbox run)
    python scripts/verify_golden.py --limit 3
    python scripts/verify_golden.py --only invoice_04.jpg
    python scripts/verify_golden.py --reset-accounting    # DELETE /invoices first
    python scripts/verify_golden.py --reuse-live          # compare already-processed run

Writes:
    reports/golden_report.json   per-file, per-field verdicts
    reports/golden_report.md     human-readable matrix

Exit code: 0 = all critical fields match, 1 = at least one critical mismatch,
2 = usage error.
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _SCRIPT_DIR.parent
TAKE_HOME = PROJECT_ROOT.parent / "take-home"
SAMPLES_DIR = TAKE_HOME / "invoices"
GOLDEN_PATH = TAKE_HOME / "golden.json"
REPORTS_DIR = PROJECT_ROOT / "reports"

# --reuse-live compares against an already-processed run (reads the real DB via
# .env / env vars). Otherwise we run in a throwaway sandbox DB so file dedup and
# stale state never interfere with a fresh verification run.
REUSE_LIVE = "--reuse-live" in sys.argv
VERIFY_ROOT = PROJECT_ROOT / "data" / "verify"
if not REUSE_LIVE:
    os.environ.setdefault("STORAGE_ROOT", str(VERIFY_ROOT / "storage"))
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{VERIFY_ROOT / 'verify.db'}")
    os.environ.setdefault("WE_WH_DIR", str(VERIFY_ROOT / "we_wh"))

sys.path.insert(0, str(PROJECT_ROOT))

from app.clients.accounting_client import AccountingClient  # noqa: E402
from app.processing.processor import InvoiceProcessor  # noqa: E402
from app.repositories.job_repository import InvoiceRepository  # noqa: E402

# Fields whose mismatch fails the file (identity + amounts + line count).
CRITICAL = [
    "partner_code", "invoice_number", "issue_date", "due_date",
    "subtotal", "tax_amount", "total_amount", "supplier_name", "line_count",
]


def norm(value) -> str:
    """NFKC + drop all whitespace; stable string key for comparison."""
    if value is None:
        return ""
    chars = (c for c in unicodedata.normalize("NFKC", str(value)) if not c.isspace())
    return "".join(chars)


def line_score(golden: dict, extracted: dict) -> int:
    score = 0
    if golden.get("amount") == extracted.get("amount"):
        score += 100
    if norm(golden.get("description")) and norm(golden.get("description")) == norm(extracted.get("description")):
        score += 20
    if golden.get("quantity") == extracted.get("quantity"):
        score += 20
    if golden.get("unit_price") == extracted.get("unit_price"):
        score += 20
    if norm(golden.get("unit")) and norm(golden.get("unit")) == norm(extracted.get("unit")):
        score += 5
    if norm(golden.get("tax_code")) and norm(golden.get("tax_code")) == norm(extracted.get("tax_code")):
        score += 10
    return score


def compare_lines(golden: list[dict], extracted: list[dict]) -> dict:
    """Greedy best-match each golden line to an extracted line. Bounded by amount."""
    results = []
    remaining = list(extracted)
    for g in golden:
        best_idx, best_score = None, -1
        for i, ex in enumerate(remaining):
            sc = line_score(g, ex)
            if sc > best_score:
                best_idx, best_score = i, sc
        if best_idx is None:
            results.append({"expected": g, "got": None,
                            "ok": False, "matches": False})
            continue
        ex = remaining.pop(best_idx)
        ok = best_score >= 100
        results.append({
            "expected": g, "got": ex, "ok": ok, "matches": True,
            "score": best_score,
            "amount_matches": g.get("amount") == ex.get("amount"),
            "description_matches": norm(g.get("description")) == norm(ex.get("description")),
            "quantity_matches": g.get("quantity") == ex.get("quantity"),
            "unit_price_matches": g.get("unit_price") == ex.get("unit_price"),
            "unit_matches": norm(g.get("unit")) == norm(ex.get("unit")),
            "tax_code_matches": norm(g.get("tax_code")) == norm(ex.get("tax_code")),
        })
    for ex in remaining:
        results.append({"expected": None, "got": ex, "ok": False, "matches": False,
                        "reason": "unexpected extra line"})
    return {
        "results": results,
        "count_expected": len(golden),
        "count_extracted": len(extracted),
        "line_count_ok": len(golden) == len(extracted),
        "all_match": all(r["ok"] for r in results) and len(golden) == len(extracted),
    }


def verify_one(file_name: str, golden: dict, processor: InvoiceProcessor, *,
               reuse_live: bool = False) -> dict:
    if reuse_live:
        return _compare_stored(file_name, golden)
    path = SAMPLES_DIR / file_name
    outcome = {
        "file": file_name,
        "processed": True,
        "status": "",
        "invoice_id": None,
        "errors": [],
        "fields": {},
        "lines_ok": False,
        "critical_failures": [],
    }
    summary = processor.process_file(str(path), file_name=file_name)
    outcome["status"] = summary.status
    outcome["errors"] = [e.get("message") for e in summary.errors]

    if summary.invoice_id is None:
        for f in CRITICAL:
            outcome["fields"][f] = {"expected": golden.get(f), "got": None, "ok": False}
        outcome["critical_failures"] = list(CRITICAL)
        return outcome

    outcome["invoice_id"] = summary.invoice_id
    inv = InvoiceRepository().get(summary.invoice_id)
    got_lines = InvoiceRepository().get_lines(summary.invoice_id) or []

    expected = {
        "partner_code": golden.get("partner_code"),
        "invoice_number": golden.get("invoice_number"),
        "issue_date": golden.get("issue_date"),
        "due_date": golden.get("due_date"),
        "subtotal": golden.get("subtotal"),
        "tax_amount": golden.get("tax_amount"),
        "total_amount": golden.get("total_amount"),
        "supplier_name": golden.get("supplier_name"),
        "line_count": len(golden.get("lines") or []),
    }
    actual = {
        "partner_code": inv.get("partner_code"),
        "invoice_number": inv.get("invoice_number"),
        "issue_date": inv.get("issue_date"),
        "due_date": inv.get("due_date"),
        "subtotal": inv.get("subtotal"),
        "tax_amount": inv.get("tax_amount"),
        "total_amount": inv.get("total_amount"),
        "supplier_name": inv.get("supplier_name"),
        "line_count": len(got_lines),
    }
    for f in CRITICAL:
        ok = _field_ok(expected[f], actual[f])
        outcome["fields"][f] = {"expected": expected[f], "got": actual[f], "ok": ok}
        if not ok:
            outcome["critical_failures"].append(f)

    outcome["lines"] = compare_lines(golden.get("lines") or [], got_lines)
    outcome["lines_ok"] = outcome["lines"]["all_match"]
    if not outcome["lines_ok"]:
        outcome["critical_failures"].append("line_count" if not outcome["lines"]["line_count_ok"]
                                            else "line_detail")
    return outcome


def _compare_stored(file_name: str, golden: dict) -> dict:
    """Compare against an already-processed invoice in the live DB."""
    from app.repositories.job_repository import InvoiceRepository, JobRepository

    outcome = {
        "file": file_name,
        "processed": False,
        "status": "",
        "invoice_id": None,
        "errors": [],
        "fields": {},
        "lines_ok": False,
        "critical_failures": [],
        "reused_live": True,
    }
    job = None
    for j in JobRepository().list_recent(limit=10_000):
        if j["file_name"] == file_name:
            job = j
            break
    if job is None:
        for f in CRITICAL:
            outcome["fields"][f] = {"expected": golden.get(f), "got": None, "ok": False}
        outcome["critical_failures"] = list(CRITICAL)
        outcome["errors"] = ["no job found in live DB for this file"]
        return outcome
    outcome["status"] = job["status"]

    invoice_id = None
    for inv in InvoiceRepository().list_recent(limit=10_000):
        if inv["job_id"] == job["id"]:
            invoice_id = inv["id"]
            break
    if invoice_id is None:
        for f in CRITICAL:
            outcome["fields"][f] = {"expected": golden.get(f), "got": None, "ok": False}
        outcome["critical_failures"] = list(CRITICAL)
        outcome["errors"] = [f"job is {job['status']}; no invoice produced"]
        return outcome

    outcome["invoice_id"] = invoice_id
    inv = InvoiceRepository().get(invoice_id)
    got_lines = InvoiceRepository().get_lines(invoice_id) or []

    expected = {
        "partner_code": golden.get("partner_code"),
        "invoice_number": golden.get("invoice_number"),
        "issue_date": golden.get("issue_date"),
        "due_date": golden.get("due_date"),
        "subtotal": golden.get("subtotal"),
        "tax_amount": golden.get("tax_amount"),
        "total_amount": golden.get("total_amount"),
        "supplier_name": golden.get("supplier_name"),
        "line_count": len(golden.get("lines") or []),
    }
    actual = {
        "partner_code": inv.get("partner_code"),
        "invoice_number": inv.get("invoice_number"),
        "issue_date": inv.get("issue_date"),
        "due_date": inv.get("due_date"),
        "subtotal": inv.get("subtotal"),
        "tax_amount": inv.get("tax_amount"),
        "total_amount": inv.get("total_amount"),
        "supplier_name": inv.get("supplier_name"),
        "line_count": len(got_lines),
    }
    for f in CRITICAL:
        ok = _field_ok(expected[f], actual[f])
        outcome["fields"][f] = {"expected": expected[f], "got": actual[f], "ok": ok}
        if not ok:
            outcome["critical_failures"].append(f)

    outcome["lines"] = compare_lines(golden.get("lines") or [], got_lines)
    outcome["lines_ok"] = outcome["lines"]["all_match"]
    if not outcome["lines_ok"]:
        outcome["critical_failures"].append("line_count" if not outcome["lines"]["line_count_ok"]
                                            else "line_detail")
    return outcome


def _field_ok(expected, actual) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return expected == actual
    return norm(expected) == norm(actual)


def _parse_args(argv: list[str]) -> dict:
    out = {"limit": None, "only": None, "reset_accounting": False, "reuse_live": False}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--limit":
            out["limit"] = int(argv[i + 1]); i += 2
        elif arg == "--only":
            out["only"] = argv[i + 1]; i += 2
        elif arg == "--reset-accounting":
            out["reset_accounting"] = True; i += 1
        elif arg == "--reuse-live":
            out["reuse_live"] = True; i += 1
        else:
            print(f"unknown argument: {arg}")
            sys.exit(2)
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _parse_args(argv)
    if not GOLDEN_PATH.exists():
        print(f"golden dataset not found: {GOLDEN_PATH}")
        return 2
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    if not args["reuse_live"]:
        try:
            AccountingClient().health()
        except Exception:
            print("WARNING: accounting API not reachable at http://localhost:8080 "
                  "-- partner comparisons will fail for most files. Start it with:")
            print("  python accounting_api.py")

    if args["reset_accounting"] and not args["reuse_live"]:
        removed = AccountingClient().delete_invoices()
        print(f"reset accounting mock: removed {removed} invoices")

    processor = InvoiceProcessor() if not args["reuse_live"] else None
    files = [n for n in sorted(golden) if (SAMPLES_DIR / n).is_file()]
    if args["only"]:
        files = [f for f in files if f == args["only"]]
        if not files:
            print(f"no sample matches '{args['only']}'"); return 2
    if args["limit"]:
        files = files[: args["limit"]]

    results = []
    for name in files:
        row = verify_one(name, golden[name], processor, reuse_live=args["reuse_live"])
        results.append(row)
        _print(row)

    _write_reports(results)
    failed = sum(1 for r in results if r["critical_failures"])
    print(f"\n{len(results) - failed}/{len(results)} files fully matched "
          f"({failed} with critical mismatches)")
    return 1 if failed else 0


def _print(row: dict) -> None:
    mark = "OK " if not row["critical_failures"] else "XX "
    f = row["fields"]
    print(f"  {mark}{row['file']:<16} -> {row['status']:<14} "
          f"failures={','.join(row['critical_failures']) or '-'}"
          + (f" partner={f.get('partner_code', {}).get('got')!r}" if "partner_code" in f else ""))


def _write_reports(results: list[dict]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "golden_report.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "count": len(results), "files": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = ["# Golden Dataset Verification Report", "",
             f"Generated: {datetime.now(timezone.utc).isoformat()}  |  files: {len(results)}", "",
             "| file | status | supplier | partner | invoice# | issue | due | subtotal | tax | total | lines | verdict |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        f = r["fields"]
        g = lambda k: f.get(k, {}).get("got")
        ok = lambda k: "Y" if f.get(k, {}).get("ok") else "N"
        verdict = "PASS" if not r["critical_failures"] else "FAIL"
        lines.append(
            f"| {r['file']} | {r['status']} | {ok('supplier_name')} {g('supplier_name')!r} "
            f"| {ok('partner_code')} {g('partner_code')} | {ok('invoice_number')} {g('invoice_number')} "
            f"| {ok('issue_date')} {g('issue_date')} | {ok('due_date')} {g('due_date')} "
            f"| {ok('subtotal')} {g('subtotal')} | {ok('tax_amount')} {g('tax_amount')} "
            f"| {ok('total_amount')} {g('total_amount')} | {'Y' if r.get('lines_ok') else 'N'} "
            f"({r.get('lines', {}).get('count_expected')}/{r.get('lines', {}).get('count_extracted')}) "
            f"| {verdict} |"
        )
    lines += ["", "Legend: Y/N per field maps to pass/fail against the golden value.", ""]
    (REPORTS_DIR / "golden_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nreport -> {REORTS / 'golden_report.md'}")


if __name__ == "__main__":
    sys.exit(main())