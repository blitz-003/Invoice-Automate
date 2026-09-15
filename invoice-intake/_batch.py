import sys, json
from pathlib import Path
sys.path.insert(0, ".")

from app.processing.processor import InvoiceProcessor


def _val(invoice: dict, name: str):
    if not invoice:
        return None
    for f in invoice.get("resolved_fields") or []:
        if f.get("name") == name and not f.get("error"):
            return f.get("value")
    return None


data_dir = Path("data")
files = sorted(p for p in data_dir.iterdir()
               if p.is_file() and p.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png"}
               and p.name.startswith("invoice_"))

processor = InvoiceProcessor()
rows = []
for f in files:
    s = processor.process_file(str(f), file_name=f.name)
    inv = s.invoice or {}
    rows.append({
        "file": f.name,
        "success": s.success,
        "status": s.status,
        "duplicate": s.duplicate,
        "reasons": s.reason_codes,
        "errors": [e.get("message") for e in s.errors],
        "supplier": _val(inv, "SellerInfo.SellerName"),
        "invoice_number": _val(inv, "Invoice.InvoiceNumber"),
        "total": _val(inv, "Invoice.TotalAmount"),
    })
    print(f"  [{'OK' if s.success else 'XX'}] {f.name:<14} -> {s.status:<13} "
          f"supplier={rows[-1]['supplier']!r} inv={rows[-1]['invoice_number']!r} "
          f"total={rows[-1]['total']!r} dup={s.duplicate} reasons={s.reason_codes}")

open("data/batch_summary.json", "w", encoding="utf-8").write(
    json.dumps(rows, ensure_ascii=False, indent=2))
print("\nsummary -> data/batch_summary.json")