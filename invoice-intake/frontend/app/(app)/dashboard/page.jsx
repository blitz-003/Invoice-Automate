"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../../lib/api";
import { fmtDate, jpy } from "../../../lib/format";
import SummaryCard from "../../../components/SummaryCard";
import StatusBadge from "../../../components/StatusBadge";

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    Promise.all([api.dashboard(), api.invoices()])
      .then(([d, inv]) => {
        if (!alive) return;
        setData({ ...d, recent: (inv.invoices || []).slice(0, 8) });
      })
      .catch((e) => {
        if (alive) setErr(String(e.message || e));
      });
    return () => {
      alive = false;
    };
  }, []);

  if (err) return <div className="notice" style={{ color: "var(--red)", background: "var(--red-soft)", borderColor: "#f5c6c6" }}>{err}</div>;
  if (!data) return <div className="empty-state"><span className="spin" /> Loading…</div>;

  const st = data.invoice_status || {};
  const rejected = (st.REJECTED || 0) + (st.FAILED || 0);
  const processing = (st.REGISTERING || 0) + (st.RECEIVED || 0);

  return (
    <div>
      <div className="summary-grid mb-lg">
        <Link href="/processed" style={{ textDecoration: "none" }}>
          <SummaryCard accent="emerald" title="Processed" count={st.REGISTERED ?? 0} sub="Registered successfully · 登録済み" />
        </Link>
        <Link href="/processing" style={{ textDecoration: "none" }}>
          <SummaryCard accent="blue" title="Processing" count={processing} sub="Currently processing · 処理中" />
        </Link>
        <SummaryCard accent="amber" title="Review" count={data.pending_review ?? 0} sub="Need your attention · 要確認">
          {data.pending_review > 0 && <span className="badge badge-warning mt-sm">Review {data.pending_review} invoice{data.pending_review > 1 ? "s" : ""}</span>}
        </SummaryCard>
        <Link href="/rejected" style={{ textDecoration: "none" }}>
          <SummaryCard accent="red" title="Rejected" count={rejected} sub="Could not be processed · 処理不可" />
        </Link>
      </div>

      <div className="card card-pad mb-lg" style={{ background: "var(--surface-soft)", borderStyle: "dashed" }}>
        <div className="between">
          <div>
            <h3 className="t-title">Upload invoices</h3>
            <p className="t-caption-sm muted mb-sm" style={{ margin: "4px 0 0" }}>
              PDF・JPG・JPEG・PNG — drop a file, or a folder, and we do the rest.
            </p>
          </div>
          <div className="spread">
            <Link href="/automate?mode=files">
              <button className="btn btn-primary">Choose Files</button>
            </Link>
            <Link href="/automate?mode=folder">
              <button className="btn btn-secondary">Choose Folder</button>
            </Link>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="pane-head">
          <span className="t-title">Recent invoices</span>
          <Link href="/processed" className="t-caption-sm">View all →</Link>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Invoice No.</th>
                <th>Supplier</th>
                <th>Date</th>
                <th>Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.recent.length === 0 && (
                <tr><td colSpan={5} className="empty-state">No invoices yet — upload one to get started.</td></tr>
              )}
              {data.recent.map((inv) => (
                <tr key={inv.id} className="clickable" onClick={() => (window.location.href = `/invoice/?id=${inv.id}`)}>
                  <td className="t-num">{inv.invoice_number || "—"}</td>
                  <td>{inv.supplier_name || "—"}</td>
                  <td className="muted">{inv.issue_date ? fmtDate(inv.issue_date) : "—"}</td>
                  <td className="t-num">{jpy(inv.total_amount)}</td>
                  <td><StatusBadge status={inv.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}