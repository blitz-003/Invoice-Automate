"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { fmtDateTime, jpy } from "../../../lib/format";
import { reasonsText } from "../../../lib/status";
import StatusBadge from "../../../components/StatusBadge";
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

export default function RejectedPage() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [confirm, setConfirm] = useState(null);
  const [reprocAction, setReprocAction] = useState(null);
  const [reprocessing, setReprocessing] = useState(false);
  const [reproResult, setReproResult] = useState(null);

  const load = useCallback(() => {
    let alive = true;
    Promise.all([api.invoices(), api.jobs()])
      .then(([inv, jb]) => {
        if (!alive) return;
        const invRows = (inv.invoices || [])
          .filter((r) => r.status === "REJECTED" || r.status === "FAILED")
          .map((r) => ({
            kind: "invoice",
            id: r.id,
            job_id: r.job_id,
            file_name: r.invoice_number ? `${r.invoice_number}${r.supplier_name ? ` · ${r.supplier_name}` : ""}` : r.id.slice(0, 8),
            label: r.invoice_number || r.id.slice(0, 8),
            second: r.supplier_name || null,
            amount: r.total_amount,
            reason: reasonsText(parseCodes(r.reason_codes)) || r.error_message || "Could not be processed.",
            created_at: r.created_at,
            status: r.status,
            invoice: r,
          }));
        const jobRows = (jb.jobs || [])
          .filter((j) => j.status === "REJECTED" || j.status === "FAILED")
          .filter((j) => !invRows.some((r) => r.job_id === j.id))
          .map((j) => ({
            kind: "job",
            id: j.id,
            job_id: j.id,
            file_name: j.file_name,
            label: j.file_name,
            second: null,
            amount: null,
            reason: j.error_message || "Could not be processed.",
            created_at: j.created_at,
            status: j.status,
          }));
        const merged = [...invRows, ...jobRows].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
        setItems(merged);
      })
      .catch((e) => alive && setErr(String(e.message || e)));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => load(), [load]);

  const doDelete = async () => {
    if (!confirm) return;
    try {
      if (confirm.kind === "invoice") await api.deleteInvoice(confirm.id);
      else await api.deleteJob(confirm.id);
    } catch (e) {
      setErr(String(e.message || e));
    }
    setConfirm(null);
    load();
  };

  const doReprocess = async () => {
    if (!reprocAction) return;
    setReprocessing(true);
    setReproResult(null);
    try {
      const res = await api.reprocess(reprocAction.job_id);
      setReproResult(res);
    } catch (e) {
      setErr(`Reprocess failed: ${e.message || e}`);
    } finally {
      setReprocessing(false);
      setReprocAction(null);
      load();
    }
  };

  const viewHref = (item) =>
    item.kind === "invoice" ? `/invoice/?id=${item.id}` : `/invoice/?job=${item.id}`;

  return (
    <div>
      <h1 className="t-lg page-title">Rejected</h1>
      <p className="page-sub">Invoices that could not be processed · 処理できなかった請求書</p>

      {err && <div className="notice" style={{ color: "var(--red)", background: "var(--red-soft)", borderColor: "#f5c6c6" }}>{err}</div>}

      {reproResult && (
        <div className="notice">
          <div>
            <div className="t-title">Reprocessed → {reproResult.status}</div>
            <div className="t-caption-sm" style={{ marginTop: 2 }}>
              {reproResult.status === "NEEDS_REVIEW"
                ? "The re-run is ready for review."
                : reproResult.status === "REGISTERED"
                  ? "The invoice was registered automatically."
                  : (reproResult.errors || []).map((e) => e.message).join(" ") || "The document still could not be processed."}
              {reproResult.invoice_id && <span style={{ marginLeft: 8 }}><a href={`/invoice/?id=${reproResult.invoice_id}`} style={{ color: "var(--blue)" }}>View</a></span>}
            </div>
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div style={{ fontSize: 30, marginBottom: 8 }} aria-hidden>✓</div>
            Nothing rejected. All invoices processed cleanly.
          </div>
        </div>
      ) : (
        items.map((item) => (
          <div className="item-row" key={item.id}>
            <span className="badge badge-danger">✕</span>
            <div className="grow" style={{ minWidth: 0 }}>
              <div className="row" style={{ gap: 8 }}>
                <span className="t-title truncate">{item.label}</span>
                {item.second && <span className="t-caption-sm muted truncate">{item.second}</span>}
                {item.amount != null && <span className="t-caption-sm t-num">{jpy(item.amount)}</span>}
              </div>
              <div className="t-caption-sm muted mt-sm">{item.reason}</div>
              <div className="t-caption-sm muted mt-sm">{fmtDateTime(item.created_at)}</div>
            </div>
            <StatusBadge status={item.status} />
            <button className="btn btn-sm btn-secondary" onClick={() => setReprocAction(item)}>Reprocess</button>
            <button className="btn btn-sm btn-secondary" onClick={() => (window.location.href = viewHref(item))}>View</button>
            <button className="btn btn-sm btn-soft-danger" onClick={() => setConfirm(item)}>Delete</button>
          </div>
        ))
      )}

      <Modal
        open={!!confirm}
        onClose={() => setConfirm(null)}
        title="Delete invoice?"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setConfirm(null)}>Cancel</button>
            <button className="btn btn-danger" onClick={doDelete}>Delete</button>
          </>
        }
      >
        <p className="t-body-sm">
          This invoice and its history will be permanently removed. It cannot be undone.
        </p>
        {confirm && (
          <div className="card" style={{ background: "var(--surface-soft)", padding: "12px 16px" }}>
            <div className="t-caption-sm t-num">{confirm.file_name}</div>
          </div>
        )}
      </Modal>
    <Modal
        open={!!reprocAction}
        onClose={() => setReprocAction(null)}
        title="Reprocess invoice?"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setReprocAction(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={doReprocess} disabled={reprocessing}>
              {reprocessing ? "Reprocessing…" : "Reprocess"}
            </button>
          </>
        }
      >
        <p className="t-body-sm">
          The stored original document will be re-read from scratch (fresh OCR + extraction) and a new
          decision will be made. The previous result for this file is discarded.
        </p>
        {reprocAction && (
          <div className="card" style={{ background: "var(--surface-soft)", padding: "12px 16px" }}>
            <div className="t-caption-sm t-num">{reprocAction.file_name}</div>
          </div>
        )}
      </Modal>
    </div>
  );
}