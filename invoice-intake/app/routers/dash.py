from __future__ import annotations

import html
import json

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.repositories.job_repository import InvoiceRepository, JobRepository, ReviewRepository
from app.routers.intake import process_upload

router = APIRouter(tags=["dash"])

_STYLE = """
:root { color-scheme: light dark; --red:#d64545; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
       background: #0f1115; color: #e6e8ee; padding: 24px; }
.wrap { max-width: 980px; margin: 0 auto; }
h1 { margin: 0 0 4px; font-size: 22px; }
a { color: #7cb3ff; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 20px 0; }
.card { background: #1a1e26; border: 1px solid #2a2f3a; border-radius: 10px; padding: 14px 16px; }
.card b { font-size: 22px; display: block; }
.card span { color: #9aa4b2; font-size: 12px; }
form.upload { background: #1a1e26; border: 1px dashed #3a4150; border-radius: 12px; padding: 18px; margin: 4px 0 20px; }
form.upload input[type=file] { color: #c8cedb; }
button, .btn { background: #2c6cf0; color: #fff; border: 0; border-radius: 8px; padding: 8px 14px;
              cursor: pointer; font-size: 14px; text-decoration: none; display: inline-block; }
table { width: 100%; border-collapse: collapse; background: #1a1e26; border: 1px solid #2a2f3a; border-radius: 10px; overflow: hidden; }
th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #242936; font-size: 13px; }
th { color: #9aa4b2; font-weight: 600; }
.badge { padding: 2px 8px; border-radius: 999px; font-size: 11px; }
.b-REGISTERED { background:#103a2a; color:#54d98a; } .b-NEEDS_REVIEW { background:#3a2a10; color:#ffd166; }
.b-REJECTED, .b-FAILED { background:#3a1010; color:#ff8a8a; } .b- { background:#242936; color:#9aa4b2; }
.muted { color: #9aa4b2; font-size: 13px; }
.msg { padding: 10px 14px; border-radius: 8px; margin: 12px 0; }
.msg.ok { background:#103a2a; color:#54d98a; } .msg.err { background:#3a1010; color:#ff8a8a; }
dl { display: grid; grid-template-columns: 180px 1fr; gap: 6px 14px; background:#1a1e26; border:1px solid #2a2f3a; border-radius:10px; padding:16px; }
dt { color:#9aa4b2; } dd { margin:0; }
"""


def _esc(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def _page(title: str, body: str, *, status_codes: dict | None = None) -> str:
    nav = (
        "<div class='muted' style='margin:6px 0 18px'>"
        "<a href='/dash'>Dashboard</a>"
        "<span style='margin:0 8px'>/</span>"
        f"{_esc(title)}"
        "</div>"
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{_esc(title)}</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>{_STYLE}</style></head><body><div class="wrap">{nav}{body}</div></body></html>"""


def _badge(status: str) -> str:
    return f'<span class="badge b-{_esc(status)}">{_esc(status or "—")}</span>'


@router.get("/dash", response_class=HTMLResponse)
def dash_page(ok: str = "", err: str = ""):
    jobs = JobRepository().list_recent(limit=200)
    inv = InvoiceRepository()
    status_counts = inv.count_by_status()
    pending = len(ReviewRepository().list_pending())

    flash = ""
    if ok:
        flash = f'<div class="msg ok">Processed OK — <a href="/dash/jobs/{_esc(ok)}">view job</a>.</div>'
    elif err:
        flash = f'<div class="msg err">Upload failed: {_esc(err)}</div>'

    cards = "".join(
        f'<div class="card"><b>{v}</b><span>{k}</span></div>'
        for k, v in [("Total jobs", len(jobs)), ("Awaiting review", pending)]
        + list(status_counts.items())
    )

    rows = []
    if not jobs:
        rows.append('<tr><td colspan="3" class="muted">No invoices yet — upload one below.</td></tr>')
    for j in jobs:
        rows.append(
            "<tr>"
            f'<td><a href="/dash/jobs/{_esc(j["id"])}">{_esc(j["file_name"])}</a></td>'
            f"<td>{_badge(j['status'])}</td>"
            f"<td class='muted'>{_esc(j['created_at'][:19].replace('T', ' '))}</td>"
            "</tr>"
        )

    body = (
        "<h1>Invoice Intake</h1>"
        "<p class='muted'>Server-rendered dashboard (no JavaScript required). Full SPA: "
        '<a href="/">SAKANA AI</a>.</p>'
        f"{flash}"
        f'<form class="upload" method="post" action="/dash/upload" enctype="multipart/form-data">'
        "<strong>Upload an invoice</strong><br><br>"
        '<input type="file" name="file" accept=".pdf,.jpg,.jpeg,.png" required> '
        '<button type="submit">Process</button></form>'
        f'<div class="cards">{cards}</div>'
        "<h3>Recent jobs</h3><table><thead><tr><th>File</th><th>Status</th><th>Created</th></tr></thead>"
        f"<tbody>{' '.join(rows)}</tbody></table>"
    )
    return HTMLResponse(_page("Dashboard", body))


@router.get("/dash/jobs/{job_id}", response_class=HTMLResponse)
def dash_job(job_id: str):
    job = JobRepository().get(job_id)
    if job is None:
        raise HTTPException(404, f"job {job_id} not found")
    inv = InvoiceRepository()
    invoice = inv.get(job_id)
    lines = inv.get_lines(job_id) if invoice else []

    fields = [
        ("Job", job.get("id")),
        ("File", job.get("file_name")),
        ("Status", job.get("status")),
        ("Error", job.get("error_message")),
    ]
    if invoice:
        fields += [
            ("Invoice #", invoice.get("invoice_number")),
            ("Supplier", invoice.get("supplier_name")),
            ("Partner", invoice.get("partner_code")),
            ("Issue date", invoice.get("issue_date")),
            ("Due date", invoice.get("due_date")),
            ("Currency", invoice.get("currency")),
            ("Subtotal", invoice.get("subtotal")),
            ("Tax", invoice.get("tax_amount")),
            ("Total", invoice.get("total_amount")),
            ("Confidence", invoice.get("confidence")),
            ("Accounting id", invoice.get("accounting_id")),
            ("Mode", invoice.get("extraction_mode")),
            ("Status", invoice.get("status")),
            ("Reason codes", invoice.get("reason_codes")),
        ]

    dl = "".join(f"<dt>{_esc(k)}</dt><dd>{_esc(v)}</dd>" for k, v in fields if v not in ("", None))

    line_rows = ""
    if lines:
        heads = "<tr><th>#</th><th>Description</th><th>Qty</th><th>Unit</th><th>Price</th><th>Amount</th><th>Tax</th></tr>"
        body_rows = "".join(
            "<tr>"
            f"<td>{_esc(l.get('position'))}</td>"
            f"<td>{_esc(l.get('description'))}</td>"
            f"<td>{_esc(l.get('quantity'))}</td>"
            f"<td>{_esc(l.get('unit'))}</td>"
            f"<td>{_esc(l.get('unit_price'))}</td>"
            f"<td>{_esc(l.get('amount'))}</td>"
            f"<td>{_esc(l.get('tax_code'))}</td>"
            "</tr>"
            for l in lines
        )
        line_rows = f"<h3>Line items ({len(lines)})</h3><table><thead>{heads}</thead><tbody>{body_rows}</tbody></table>"

    body = f"<h1>{_esc(job.get('file_name'))}</h1><dl>{dl}</dl>{line_rows}"
    return HTMLResponse(_page(f"Job {job_id[:8]}", body))


@router.post("/dash/upload")
async def dash_upload(file: UploadFile = File(...)):
    try:
        resp = await process_upload(file)
        payload = json.loads(resp.body.decode("utf-8"))
        job_id = payload.get("job_id", "") if isinstance(payload, dict) else ""
    except HTTPException as exc:
        return RedirectResponse(f"/dash?err={exc.detail}", status_code=303)
    except Exception as exc:  # noqa: BLE001
        return RedirectResponse(f"/dash?err={type(exc).__name__}", status_code=303)
    return RedirectResponse(f"/dash?ok={job_id}", status_code=303)