"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../../lib/api";
import { fmtDateTime, jpy } from "../../../lib/format";
import { reasonsText } from "../../../lib/status";
import StatusBadge from "../../../components/StatusBadge";
import DocViewer from "../../../components/DocViewer";
import Modal from "../../../components/Modal";

function parseCodes(raw) {
  if (!raw) return [];
  try {
    const v = JSON.parse(raw);
    return Array.isArray(v) ? v : v ? [v] : [];
  } catch {
    return [String(raw)];
  }
}

export default function InvoiceDetailPage() {
  const [q, setQ] = useState({ id: null, job: null });
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [invoice, setInvoice] = useState(null);
  const [document, setDocument] = useState(null);
  const [tokens, setTokens] = useState([]);
  const [review, setReview] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const [reprocOpen, setReprocOpen] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [reproNotices, setReproNotices] = useState([]);

  useEffect(() => {
    const s = new URLSearchParams(window.location.search);
    setQ({ id: s.get("id"), job: s.get("job") });
  }, []);

  useEffect(() => {
    if (!q.id && !q.job) return;
    let alive = true;
    const load = async () => {
      try {
        let inv = null;
        let job = null;
        if (q.id) {
          inv = await api.invoice(q.id);
          setInvoice(inv);
          setReview(inv.review || null);
        }
        if (q.job) {
          job = await api.job(q.job);
          const doc = await api.jobDocument(q.job).catch(() => null);
          if (alive) setDocument(doc);
          try {
            const ev = await api.jobEvidence(q.job);
            if (alive) setTokens(ev.tokens || []);
          } catch { /* none */ }
        }
        if (!job && inv?.job_id) {
          try {
            const doc = await api.jobDocument(inv.job_id);
            if (alive) setDocument(doc);
          } catch { /* none */ }
          try {
            const ev = await api.jobEvidence(inv.job_id);
            if (alive) setTokens(ev.tokens || []);
          } catch { /* none */ }
        }
        if (alive) setLoading(false);
      } catch (e) {
        if (alive) {
          setErr(String(e.message || e));
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      alive = false;
    };
  }, [q.id, q.job]);

  const doDelete = async () => {
    setDeleting(true);
    try {
      if (q.id) await api.deleteInvoice(q.id);
      else if (q.job) await api.deleteJob(q.job);
      setDeleted(true);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setDeleting(false);
      setConfirmOpen(false);
    }
  };

  const doReprocess = async () => {
    const jobId = q.job || invoice?.job_id;
    if (!jobId) return;
    setReprocessing(true);
    try {
      const res = await api.reprocess(jobId);
      setReproNotices((n) => [...n, `Reprocessed → ${res.status}${res.invoice_id ? ` · <a href="javascript:window.location.reload()">reload</a>` : ""}`]);
      if (res.status === "NEEDS_REVIEW") {
        window.location.href = "/review/";
        return;
      }
      if (res.status === "REGISTERED") {
        window.location.href = "/processed/";
        return;
      }
      if (res.invoice_id) window.location.href = `/invoice/?id=${res.invoice_id}`;
      else window.location.reload();
    } catch (e) {
      setErr(`Reprocess failed: ${e.message || e}`);
      setReprocOpen(false);
    } finally {
      setReprocessing(false);
    }
  };

  if (deleted) {
    return (
      <div style={{ maxWidth: 520 }}>
        <div className="banner-success">
          <span style={{ width: 40, height: 40, borderRadius: "50%", background: "#fff", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 20, flex: "none" }}>✓</span>
          <div>
            <div className="t-title">Invoice deleted</div>
            <div className="t-caption-sm" style={{ color: "var(--emerald)" }}>The invoice and its history were removed.</div>
          </div>
        </div>
        <div className="spread">
          <Link href="/rejected/"><button className="btn btn-secondary">Back to Rejected</button></Link>
          <Link href="/dashboard/"><button className="btn btn-primary">Dashboard</button></Link>
        </div>
      </div>
    );
  }

  if (loading) return <div className="empty-state"><span className="spin" /> Loading…</div>;
  if (err) return <div className="notice" style={{ color: "var(--red)", background: "var(--red-soft)", borderColor: "#f5c6c6" }}>{err}</div>;
  if (!invoice && !q.job) return null;

  const codes = invoice ? parseCodes(invoice.reason_codes) : [];
  const lines = invoice?.lines || [];

  return (
    <div>
      <div className="between mb-md" style={{ flexWrap: "wrap", gap: 12 }}>
        <div className="row" style={{ gap: 12 }}>
          <h1 className="t-lg page-title" style={{ margin: 0 }}>
            {invoice ? invoice.invoice_number || "Invoice" : q.job ? "Rejected document" : "Invoice"}
          </h1>
          {invoice && <StatusBadge status={invoice.status} showJp />}
        </div>
        <div className="row" style={{ gap: 10 }}>
          {(invoice?.job_id || q.job) && (
            <button className="btn btn-sm btn-secondary" onClick={() => setReprocOpen(true)} disabled={reprocessing}>
              Reprocess
            </button>
          )}
          <button className="btn btn-sm btn-soft-danger" onClick={() => setConfirmOpen(true)} disabled={deleting}>
            Delete
          </button>
        </div>
      </div>

      {reproNotices.length > 0 && (
        <div className="notice mb-md" dangerouslySetInnerHTML={{ __html: reproNotices.join("<br/>") }} />
      )}

      <div className="review-grid">
        <div className="col" style={{ gap: 16 }}>
          {invoice && (
            <div className="pane">
              <div className="pane-head"><span className="t-title">INVOICE DATA</span></div>
              <div className="pane-body">
                <Row k="Supplier" v={invoice.supplier_name} />
                <Row k="Invoice Number" v={invoice.invoice_number} />
                <Row k="Issue Date" v={invoice.issue_date} />
                <Row k="Due Date" v={invoice.due_date} />
                <Row k="Currency" v={invoice.currency} />
                <Row k="Subtotal" v={jpy(invoice.subtotal)} />
                <Row k="Tax" v={jpy(invoice.tax_amount)} />
                <Row k="Total" v={jpy(invoice.total_amount)} />
                <Row k="Accounting ID" v={invoice.accounting_id} />
                {codes.length > 0 && <Row k="Reason" v={reasonsText(codes)} />}
              </div>
            </div>
          )}

          {!invoice && q.job && <RejectedJobCard jobId={q.job} />}

          {lines.length > 0 && (
            <div className="pane">
              <div className="pane-head"><span className="t-title">Line items ({lines.length})</span></div>
              <div className="pane-body" style={{ paddingTop: 12 }}>
                <table className="lines-table">
                  <thead>
                    <tr><th>Description</th><th className="qty">Qty</th><th>Unit</th><th className="price">Unit Price</th><th className="price">Amount</th><th>Tax</th></tr>
                  </thead>
                  <tbody>
                    {lines.map((l, i) => (
                      <tr key={i}>
                        <td>{l.description}</td>
                        <td className="t-num">{l.quantity ?? "—"}</td>
                        <td>{l.unit || "—"}</td>
                        <td className="price t-num">{l.unit_price != null ? jpy(l.unit_price) : "—"}</td>
                        <td className="price t-num">{l.amount != null ? jpy(l.amount) : "—"}</td>
                        <td>{l.tax_code}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {invoice && (invoice.audit || []).length > 0 && (
            <div className="pane">
              <div className="pane-head"><span className="t-title">History</span>
                <span className="t-caption-sm muted">what changed and when</span>
              </div>
              <div className="pane-body" style={{ paddingTop: 8 }}>
                <table className="table">
                  <thead>
                    <tr><th>Field</th><th>From</th><th>To</th><th>By</th><th>When</th></tr>
                  </thead>
                  <tbody>
                    {invoice.audit.map((a, i) => (
                      <tr key={i}>
                        <td className="t-caption-sm">{a.field_name}</td>
                        <td className="t-caption-sm muted">{a.old_value || "—"}</td>
                        <td className="t-caption-sm">{a.new_value || "—"}</td>
                        <td className="t-caption-sm muted">{a.actor || "—"}</td>
                        <td className="t-caption-sm muted">{a.timestamp ? fmtDateTime(a.timestamp) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        <div>
          <DocViewer
            pages={document?.pages || []}
            tokens={tokens}
            docLabel={document?.sources?.[0]?.file}
          />
        </div>
      </div>

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Delete invoice?"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setConfirmOpen(false)}>Cancel</button>
            <button className="btn btn-danger" onClick={doDelete} disabled={deleting}>
              {deleting ? "Deleting…" : "Delete"}
            </button>
          </>
        }
      >
        <p className="t-body-sm">
          This invoice, its source document and its history will be permanently removed from the system.
        </p>
      </Modal>

      <Modal
        open={reprocOpen}
        onClose={() => setReprocOpen(false)}
        title="Reprocess this document?"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setReprocOpen(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={doReprocess} disabled={reprocessing}>
              {reprocessing ? "Reprocessing…" : "Reprocess"}
            </button>
          </>
        }
      >
        <p className="t-body-sm">
          The stored original document will be re-read from scratch (fresh OCR + extraction) and a new
          decision will be made. The previous result is discarded.
        </p>
      </Modal>
    </div>
  );
}

function RejectedJobCard({ jobId }) {
  const [job, setJob] = useState(null);
  useEffect(() => {
    let alive = true;
    api.job(jobId)
      .then((j) => alive && setJob(j))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [jobId]);

  return (
    <div className="pane">
      <div className="pane-head">
        <span className="t-title">REJECTED</span>
        <StatusBadge status="REJECTED" />
      </div>
      <div className="pane-body">
        <Row k="File" v={job?.file_name} />
        <Row k="Error" v={job?.error_message || reasonsText([job?.error_code])} />
        {job?.error_code && <Row k="Code" v={job.error_code} />}
        <Row k="Created" v={job?.created_at ? fmtDateTime(job.created_at) : null} />
      </div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="between" style={{ padding: "7px 0", borderBottom: "1px solid var(--hairline-soft)" }}>
      <span className="t-caption-sm muted">{k}</span>
      <span className="t-caption-sm t-num" style={{ textAlign: "right", maxWidth: "70%" }}>{v || "—"}</span>
    </div>
  );
}