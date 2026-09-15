"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../../lib/api";
import { jpy } from "../../../lib/format";
import { reasonsText } from "../../../lib/status";

function parseCodes(raw) {
  if (!raw) return [];
  try {
    const v = JSON.parse(raw);
    return Array.isArray(v) ? v : v ? [v] : [];
  } catch {
    return [String(raw)];
  }
}

export default function ReviewPage() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    api.reviewQueue()
      .then((d) => alive && setItems((d.items || []).filter((i) => i.status === "PENDING")))
      .catch((e) => alive && setErr(String(e.message || e)));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div>
      <h1 className="t-lg page-title">Review</h1>
      <p className="page-sub">
        {items.length > 0
          ? `${items.length} invoice${items.length > 1 ? "s" : ""} need your attention`
          : "Nothing needs your attention right now"}
      </p>

      {err && <div className="notice" style={{ color: "var(--red)", background: "var(--red-soft)", borderColor: "#f5c6c6" }}>{err}</div>}

      {items.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div style={{ fontSize: 30, marginBottom: 8 }} aria-hidden>✓</div>
            All clear — no invoices need review.
            <div className="t-caption-sm muted mt-sm">Only invoices the system could not confirm appear here.</div>
          </div>
        </div>
      ) : (
        items.map((item) => {
          const inv = item.invoice || {};
          const codes = parseCodes(item.reason_codes);
          return (
            <div className="item-row" key={item.id}>
              <span className="badge badge-warning">⚠</span>
              <div className="grow" style={{ minWidth: 0 }}>
                <div className="row" style={{ gap: 8 }}>
                  <span className="t-title truncate">{inv.file_name || "Invoice"}</span>
                </div>
                <div className="mt-sm" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "4px 20px" }}>
                  <div><div className="t-caption-sm muted">Supplier</div>{inv.supplier_name || "—"}</div>
                  <div><div className="t-caption-sm muted">Invoice</div>{inv.invoice_number || "—"}</div>
                  <div><div className="t-caption-sm muted">Amount</div><span className="t-num">{jpy(inv.total_amount)}</span></div>
                </div>
                <div className="t-caption-sm mt-sm" style={{ color: "var(--amber)" }}>
                  {reasonsText(codes)}
                </div>
              </div>
              <Link href={`/review-detail/?id=${item.id}`}>
                <button className="btn btn-primary">Review</button>
              </Link>
            </div>
          );
        })
      )}
      {items.length > 0 && (
        <div className="card card-pad mt-lg" style={{ background: "var(--surface-soft)" }}>
          <p className="t-caption-sm muted" style={{ margin: 0 }}>
            We only ask you to review what needs a human. Confirm the value against the document on the left, fix it if needed, then register.
          </p>
        </div>
      )}
    </div>
  );
}