"use client";

import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { fmtDateTime } from "../../../lib/format";
import { FINAL_STATUSES, BUSINESS_STEPS } from "../../../lib/status";
import StatusBadge from "../../../components/StatusBadge";

export default function ProcessingPage() {
  const [jobs, setJobs] = useState([]);
  const [err, setErr] = useState("");
  const [stoppingId, setStoppingId] = useState(null);

  useEffect(() => {
    let alive = true;
    api.jobs()
      .then((d) => alive && setJobs((d.jobs || []).filter((j) => !FINAL_STATUSES.has(j.status))))
      .catch((e) => alive && setErr(String(e.message || e)));
    return () => {
      alive = false;
    };
  }, []);

  const stop = async (id) => {
    if (!window.confirm("Stop processing this invoice? It will be marked as stopped and removed from the processing list.")) return;
    setStoppingId(id);
    setErr("");
    try {
      await api.stopJob(id);
      setJobs((list) => list.filter((j) => j.id !== id));
    } catch (e) {
      setErr(`Stop failed: ${e.message || e}`);
    } finally {
      setStoppingId(null);
    }
  };

  return (
    <div>
      <h1 className="t-lg page-title">Processing</h1>
      <p className="page-sub">
        {jobs.length > 0 ? `${jobs.length} invoice${jobs.length > 1 ? "s" : ""} currently processing` : "No invoices are processing right now"}
      </p>

      {err && <div className="notice" style={{ color: "var(--red)", background: "var(--red-soft)", borderColor: "#f5c6c6" }}>{err}</div>}

      {jobs.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div style={{ fontSize: 30, marginBottom: 8 }} aria-hidden>⟳</div>
            Nothing processing right now.
            <div className="t-caption-sm muted mt-sm">
              You can upload invoices from the <a href="/automate">Automate</a> page.
            </div>
          </div>
        </div>
      ) : (
        jobs.map((j) => (
          <div className="card mb-md" key={j.id}>
            <div className="pane-body">
              <div className="between">
                <div className="row" style={{ gap: 10 }}>
                  <span style={{ color: "var(--blue)" }}>⟳</span>
                  <span className="t-title truncate">{j.file_name}</span>
                </div>
                <div className="row" style={{ gap: 8 }}>
                  <StatusBadge status={j.status} />
                  <button
                    className="btn btn-xs btn-danger"
                    onClick={() => stop(j.id)}
                    disabled={stoppingId === j.id}
                  >
                    {stoppingId === j.id ? "Stopping…" : "Stop"}
                  </button>
                </div>
              </div>
              <div className="t-caption-sm muted mt-md">
                Started {fmtDateTime(j.created_at)}
              </div>
              <div className="row mt-md" style={{ gap: 6, flexWrap: "wrap" }}>
                {BUSINESS_STEPS.map((s, i) => {
                  const active = true;
                  return (
                    <span
                      key={s}
                      className="badge"
                      style={
                        active
                          ? { background: "var(--blue-soft)", color: "var(--blue-strong)" }
                          : { background: "var(--surface-strong)", color: "var(--muted)" }
                      }
                    >
                      {i + 1}. {s}
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}