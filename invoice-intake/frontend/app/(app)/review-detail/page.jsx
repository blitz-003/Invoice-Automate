"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api } from "../../../lib/api";
import { jpy } from "../../../lib/format";
import { reasonsText } from "../../../lib/status";
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

function toVal(v) {
  return v === null || v === undefined ? "" : String(v);
}

function num(v) {
  const n = parseFloat(String(v).replace(/[^0-9.-]/g, ""));
  return Number.isNaN(n) ? null : n;
}

const FIELDS = [
  { key: "supplier_name", label: "Supplier", hint: "取引先" },
  { key: "invoice_number", label: "Invoice Number", hint: "請求書番号" },
  { key: "issue_date", label: "Issue Date", hint: "請求日" },
  { key: "due_date", label: "Due Date", hint: "支払期限" },
  { key: "currency", label: "Currency", hint: "通貨" },
];

export default function ReviewDetailPage() {
  const [itemId, setItemId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [item, setItem] = useState(null);
  const [invoice, setInvoice] = useState(null);
  const [document, setDocument] = useState(null);
  const [tokens, setTokens] = useState([]);
  const [form, setForm] = useState({});
  const [lines, setLines] = useState([]);
  const [highlight, setHighlight] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [done, setDone] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    setItemId(q.get("id"));
  }, []);

  useEffect(() => {
    if (!itemId) return;
    let alive = true;
    const load = async () => {
      try {
        const queue = await api.reviewQueue();
        const found = (queue.items || []).find((i) => String(i.id) === String(itemId));
        if (!alive) return;
        if (!found) {
          setErr("Review item not found — it may already be resolved.");
          setLoading(false);
          return;
        }
        setItem(found);
        const inv = await api.invoice(found.invoice_id);
        if (!alive) return;
        setInvoice(inv);
        setForm({
          supplier_name: toVal(inv.supplier_name),
          invoice_number: toVal(inv.invoice_number),
          issue_date: toVal(inv.issue_date),
          due_date: toVal(inv.due_date),
          currency: toVal(inv.currency),
          subtotal: toVal(inv.subtotal),
          tax_amount: toVal(inv.tax_amount),
          total_amount: toVal(inv.total_amount),
        });
        setLines((inv.lines || []).map((l) => ({ ...l })));

        if (inv.job_id) {
          try {
            const doc = await api.jobDocument(inv.job_id);
            if (alive) setDocument(doc);
          } catch {
            /* no doc artifacts */
          }
          try {
            const ev = await api.jobEvidence(inv.job_id);
            if (alive) setTokens(ev.tokens || []);
          } catch {
            /* no evidence yet */
          }
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
  }, [itemId]);

  const codes = useMemo(() => (item ? parseCodes(item.reason_codes) : []), [item]);
  const dropHighlight = () => setHighlight(null);

  const setField = (k, v) => {
    setForm((f) => ({ ...f, [k]: v }));
    setDirty(true);
  };

  const setLine = (idx, k, v) => {
    setLines((ls) => {
      const next = ls.map((l, i) => (i === idx ? { ...l, [k]: v } : l));
      const sub = next.reduce((s, l) => s + (num(l.amount) || 0), 0);
      setForm((f) => ({ ...f, subtotal: sub }));
      return next;
    });
    setDirty(true);
  };

  const save = async () => {
    setSaving(true);
    setNotice("");
    try {
      const user = JSON.parse(localStorage.getItem("sakana.user") || "{}");
      const reviewer = user.email || "demo";
      for (const [k, v] of Object.entries(form)) {
        if (FIELDS.some((f) => f.key === k)) {
          await api.editField(invoice.id, k, v, reviewer, "review edit");
        }
      }
      await api.editField(invoice.id, "subtotal", toVal(form.subtotal), reviewer, "review edit");
      await api.editField(invoice.id, "tax_amount", toVal(form.tax_amount), reviewer, "review edit");
      await api.editField(invoice.id, "total_amount", toVal(form.total_amount), reviewer, "review edit");
      const cleanLines = lines.map((l) => ({
        description: l.description, quantity: num(l.quantity),
        unit: l.unit || "", unit_price: num(l.unit_price), amount: num(l.amount), tax_code: l.tax_code || "T10",
      }));
      await api.patchLines?.(invoice.id, cleanLines, reviewer, "review edit");
      setDirty(false);
    } catch (e) {
      setNotice(`Save failed: ${e.message || e}`);
    } finally {
      setSaving(false);
    }
  };

  const register = async (comment) => {
    setSaving(true);
    try {
      const user = JSON.parse(localStorage.getItem("sakana.user") || "{}");
      const res = await api.approveReview(item.id, user.email || "demo", comment || "");
      setDone(true);
    } catch (e) {
      setNotice(`Registration failed: ${e.message || e}`);
    } finally {
      setSaving(false);
      setConfirmOpen(false);
    }
  };

  const rejectWorkflow = async () => {
    setSaving(true);
    try {
      const user = JSON.parse(localStorage.getItem("sakana.user") || "{}");
      await api.rejectReview(item.id, user.email || "demo", rejectReason);
      window.location.href = "/review/";
    } catch (e) {
      setNotice(`Reject failed: ${e.message || e}`);
      setSaving(false);
    }
  };

  if (done) {
    return (
      <div style={{ maxWidth: 560 }}>
        <div className="banner-success">
          <span style={{ width: 44, height: 44, borderRadius: "50%", background: "#fff", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 22, flex: "none" }}>✓</span>
          <div>
            <div className="t-title">Registration complete</div>
            <div className="t-caption-sm" style={{ color: "var(--emerald)" }}>The invoice has been successfully registered.</div>
          </div>
        </div>
        <div className="card card-pad mb-lg">
          <Row k="Invoice" v={(invoice || {}).invoice_number || "—"} />
          <Row k="Amount" v={jpy((invoice || {}).total_amount)} />
          <Row k="Status" v="登録済み (Registered)" />
        </div>
        <div className="spread">
          <Link href="/review/"><button className="btn btn-secondary">Back to Review</button></Link>
          <Link href="/processed/"><button className="btn btn-secondary">View Processed Invoices</button></Link>
          <Link href="/dashboard/"><button className="btn btn-primary">Dashboard</button></Link>
        </div>
      </div>
    );
  }

  if (loading) return <div className="empty-state"><span className="spin" /> Loading invoice…</div>;
  if (err) return <div className="notice" style={{ color: "var(--red)", background: "var(--red-soft)", borderColor: "#f5c6c6" }}>{err}</div>;
  if (!invoice) return null;

  return (
    <div>
      <div className="between mb-md" style={{ flexWrap: "wrap", gap: 12 }}>
        <h1 className="t-lg page-title" style={{ margin: 0 }}>Review invoice</h1>
        <button className="btn btn-primary" onClick={() => setConfirmOpen(true)} disabled={saving}>
          ✓ Register Invoice
        </button>
      </div>

      {codes.length > 0 && (
        <div className="notice">
          <span aria-hidden style={{ fontSize: 18 }}>⚠</span>
          <div>
            <div className="t-title">確認が必要です</div>
            <div className="t-caption-sm" style={{ marginTop: 2 }}>{reasonsText(codes)}</div>
          </div>
        </div>
      )}
      {notice && (
        <div className="notice" style={{ color: "var(--red)", background: "var(--red-soft)", borderColor: "#f5c6c6" }}>{notice}</div>
      )}

      <div className="review-grid">
        <div className="pane">
          <div className="pane-head">
            <span className="t-title">INVOICE DATA</span>
            {dirty && <span className="badge badge-warning">Unsaved changes</span>}
          </div>
          <div className="pane-body">
            {FIELDS.map((f) => (
              <FieldRow
                key={f.key}
                label={f.label}
                hint={f.hint}
                value={form[f.key]}
                onFocus={() => setHighlight({ label: f.label, value: form[f.key] })}
                onChange={(v) => setField(f.key, v)}
              />
            ))}

            <div className="field">
              <span className="label">Line Items</span>
              <div className="lines-wrap">
                <table className="lines-table">
                  <thead>
                    <tr>
                      <th>Description</th><th className="qty">Qty</th><th>Unit</th>
                      <th className="price">Unit Price</th><th className="price">Amount</th><th>Tax</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((l, i) => (
                      <tr key={i}>
                        <td>
                          <input
                            className="num-input"
                            value={toVal(l.description)}
                            onFocus={() => setHighlight({ label: "Line item", value: toVal(l.description) })}
                            onChange={(e) => setLine(i, "description", e.target.value)}
                          />
                        </td>
                        <td><input className="num-input" inputMode="numeric" value={toVal(l.quantity)} onChange={(e) => setLine(i, "quantity", e.target.value)} /></td>
                        <td><input className="num-input" value={toVal(l.unit)} onChange={(e) => setLine(i, "unit", e.target.value)} /></td>
                        <td><input className="num-input" inputMode="numeric" value={toVal(l.unit_price)} onChange={(e) => setLine(i, "unit_price", e.target.value)} /></td>
                        <td><input className="num-input" inputMode="numeric" value={toVal(l.amount)} onChange={(e) => setLine(i, "amount", e.target.value)} /></td>
                        <td><input className="num-input" style={{ width: 64 }} value={toVal(l.tax_code)} onChange={(e) => setLine(i, "tax_code", e.target.value)} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div
              className="total-row"
              onMouseEnter={(e) => setHighlight({ label: "Subtotal", value: toVal(form.subtotal) })}
              onMouseLeave={dropHighlight}
            >
              <span className="t-caption-sm muted">Subtotal</span>
              <input className="num-input" style={{ width: 120, textAlign: "right" }} value={toVal(form.subtotal)} onChange={(e) => setField("subtotal", e.target.value)} />
            </div>
            <div className="total-row" onMouseEnter={(e) => setHighlight({ label: "Tax", value: toVal(form.tax_amount) })} onMouseLeave={dropHighlight}>
              <span className="t-caption-sm muted">Tax</span>
              <input className="num-input" style={{ width: 120, textAlign: "right" }} value={toVal(form.tax_amount)} onChange={(e) => setField("tax_amount", e.target.value)} />
            </div>
            <div className="total-row grand" onMouseEnter={(e) => setHighlight({ label: "Total", value: toVal(form.total_amount) })} onMouseLeave={dropHighlight}>
              <span>Total</span>
              <input className="num-input" style={{ width: 140, textAlign: "right", fontWeight: 700 }} value={toVal(form.total_amount)} onChange={(e) => setField("total_amount", e.target.value)} />
            </div>

            <div className="spread mt-lg">
              <button className="btn btn-secondary" onClick={() => setRejectOpen(true)} disabled={saving}>Reject</button>
              <button className="btn btn-soft" onClick={save} disabled={saving || !dirty}>
                {saving ? "Saving…" : "Save"}
              </button>
              <button className="btn btn-primary" onClick={() => setConfirmOpen(true)} disabled={saving}>
                ✓ Register Invoice
              </button>
            </div>
          </div>
        </div>

        <div>
          <DocViewer
            pages={document?.pages || []}
            tokens={tokens}
            highlight={highlight}
            docLabel={document?.sources?.[0]?.file}
          />
        </div>
      </div>

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Register invoice?"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setConfirmOpen(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={() => register("registered after review")} disabled={saving}>
              {saving ? "Registering…" : "Register"}
            </button>
          </>
        }
      >
        <p className="t-body-sm muted">This invoice will be registered in the accounting system.</p>
        <div className="card" style={{ background: "var(--surface-soft)", padding: "14px 18px" }}>
          <Row k="Supplier" v={form.supplier_name} />
          <Row k="Invoice" v={form.invoice_number} />
          <Row k="Total" v={jpy(form.total_amount)} />
        </div>
      </Modal>

      <Modal
        open={rejectOpen}
        onClose={() => { setRejectOpen(false); setRejectReason(""); }}
        title="Reject invoice"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => { setRejectOpen(false); setRejectReason(""); }}>Cancel</button>
            <button className="btn btn-danger" onClick={rejectWorkflow} disabled={saving || !rejectReason.trim()}>
              {saving ? "Rejecting…" : "Reject Invoice"}
            </button>
          </>
        }
      >
        <p className="t-body-sm muted">The document will not be registered. Tell us why (optional reason shown to the team).</p>
        <textarea className="input" rows={3} placeholder="Reason（例: 画像が不鮮明 / 内容を確認できない）" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
      </Modal>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="between" style={{ padding: "6px 0", borderBottom: "1px solid var(--hairline-soft)" }}>
      <span className="t-caption-sm muted">{k}</span>
      <span className="t-caption-sm t-num">{v || "—"}</span>
    </div>
  );
}

function FieldRow({ label, hint, value, onChange, onFocus }) {
  return (
    <div className="field">
      <label className="label">{label}
        {hint && <span style={{ marginLeft: 6, textTransform: "none", fontWeight: 500 }}>· {hint}</span>}
      </label>
      <input className="input" value={value} onChange={(e) => onChange(e.target.value)} onFocus={onFocus} aria-label={label} />
    </div>
  );
}