"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { api } from "../../../lib/api";
import { reasonsText } from "../../../lib/status";
import SummaryCard from "../../../components/SummaryCard";

const ACCEPTED = [".pdf", ".jpg", ".jpeg", ".png"];
const MAX_MB = 20;
const CONCURRENCY = 3;

function validate(file) {
  const ext = (file.name.toLowerCase().match(/\.[a-z0-9]+$/)?.[0]) || "";
  if (!ACCEPTED.includes(ext)) {
    return { ok: false, reason: "Unsupported file type. Use PDF, JPG, JPEG or PNG.", reasonJp: "対応していない形式です（PDF・JPG・JPEG・PNGのみ）" };
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    return { ok: false, reason: `File exceeds ${MAX_MB}MB limit.`, reasonJp: "20MBを超えるファイルは処理できません。" };
  }
  return { ok: true, reason: "" };
}

const PHASE_SELECT = "select";
const PHASE_CONFIRM = "confirm";
const PHASE_PROCESSING = "processing";
const PHASE_SUMMARY = "summary";

export default function AutomatePage() {
  const [phase, setPhase] = useState(PHASE_SELECT);
  const [files, setFiles] = useState([]); // {id, file, valid, reason}
  const [results, setResults] = useState({}); // id -> outcome
  const [mode, setMode] = useState(null);
  const filesInputRef = useRef(null);
  const folderInputRef = useRef(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    setMode(q.get("mode"));
  }, []);

  useEffect(() => {
    if (!mode) return;
    const t = setTimeout(() => {
      if (mode === "files") filesInputRef.current?.click();
      if (mode === "folder") folderInputRef.current?.click();
    }, 80);
    return () => clearTimeout(t);
  }, [mode]);

  const pending = useMemo(
    () => files.filter((f) => !results[f.id]).map((f) => f.id),
    [files, results]
  );
  const running = pending.filter((id) => results[id]?.state === "running").length;
  const done = files.length - pending.length;

  const pick = (list) => {
    const picked = Array.from(list || []).map((file) => {
      const v = validate(file);
      return { id: `${file.name}-${file.size}-${file.lastModified}`, file, valid: v.ok, reason: v.reason, reasonJp: v.reasonJp };
    });
    setFiles(picked);
    setResults({});
    setPhase(PHASE_CONFIRM);
  };

  const startProcessing = () => {
    setPhase(PHASE_PROCESSING);
    const validIds = files.filter((f) => f.valid).map((f) => f.id);
    setResults(Object.fromEntries(validIds.map((id) => [id, { state: "waiting" }])));
  };

  useEffect(() => {
    if (phase !== PHASE_PROCESSING) return;
    const validIds = files.filter((f) => f.valid).map((f) => f.id);
    // grow the pool as slots free up
    const timer = setInterval(async () => {
      const vacant = validIds.length - Object.values(results).filter((r) => r.state === "done").length;
      if (vacant <= 0) {
        clearInterval(timer);
        setPhase((p) => p === PHASE_PROCESSING ? PHASE_SUMMARY : p);
        return;
      }
      const next = validIds.find((id) => results[id]?.state === "waiting");
      if (next && Object.values(results).filter((r) => r.state === "running").length < CONCURRENCY) {
        setResults((r) => ({ ...r, [next]: { state: "running" } }));
        const f = files.find((x) => x.id === next);
        try {
          const summary = await api.upload(f.file);
          const outcome = summarize(summary);
          setResults((r) => ({ ...r, [next]: { state: "done", ...outcome } }));
        } catch (e) {
          setResults((r) => ({ ...r, [next]: { state: "done", status: "REJECTED", error: String(e.message || e) } }));
        }
      }
    }, 350);
    return () => clearInterval(timer);
  }, [phase, results, files]);

  const summaryCounts = useMemo(() => {
    const c = { REGISTERED: 0, NEEDS_REVIEW: 0, REJECTED: 0 };
    Object.values(results).forEach((r) => {
      if (r.status === "REGISTERED") c.REGISTERED += 1;
      else if (r.status === "NEEDS_REVIEW") c.NEEDS_REVIEW += 1;
      else if (r.status === "REJECTED" || r.status === "FAILED") c.REJECTED += 1;
    });
    return c;
  }, [results]);

  const validCount = files.filter((f) => f.valid).length;
  const invalidCount = files.length - validCount;

  return (
    <div>
      {phase === PHASE_SELECT && (
        <SelectView
          mode={mode}
          onFiles={() => filesInputRef.current?.click()}
          onFolder={() => folderInputRef.current?.click()}
        />
      )}

      {phase === PHASE_CONFIRM && (
        <ConfirmView
          files={files}
          validCount={validCount}
          invalidCount={invalidCount}
          onCancel={() => setPhase(PHASE_SELECT)}
          onStart={startProcessing}
        />
      )}

      {phase === PHASE_PROCESSING && (
        <ProcessingView
          files={files}
          results={results}
          done={done}
          total={validCount}
        />
      )}

      {phase === PHASE_SUMMARY && (
        <SummaryView counts={summaryCounts} files={files} results={results} />
      )}

      <input
        ref={filesInputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        multiple
        className="hidden"
        onChange={(e) => pick(e.target.files)}
      />
      <input
        ref={folderInputRef}
        type="file"
        className="hidden"
        multiple
        webkitdirectory=""
        directory=""
        onChange={(e) => pick(e.target.files)}
      />
    </div>
  );
}

function summarize(summary) {
  const s = summary || {};
  const status = s.status || (s.success ? "REGISTERED" : "REJECTED");
  return {
    job_id: s.job_id,
    invoice_id: s.invoice_id || null,
    status,
    note: (s.errors || []).map((e) => e.message).join(" ") || "",
    reason_codes: s.reason_codes || [],
    registered: s.accounting_id ? `Accounting id: ${s.accounting_id}` : "",
  };
}

function SelectView({ mode, onFiles, onFolder }) {
  return (
    <div>
      <h1 className="t-lg page-title">Automate</h1>
      <p className="page-sub">Choose the invoices to process. We read them, check them, and register the ones that are clear.</p>
      <div className="summary-grid">
        <div className="card card-pad upload-zone" onClick={onFiles} style={{ textAlign: "center" }}>
          <div style={{ fontSize: 34 }} aria-hidden>📄</div>
          <div className="t-title mt-sm">Choose Files</div>
          <div className="t-caption-sm muted mt-sm">Select one or more PDF / JPG / PNG invoices</div>
          <button className="btn btn-primary mt-lg">Choose Files</button>
        </div>
        <div className="card card-pad upload-zone" onClick={onFolder} style={{ textAlign: "center" }}>
          <div style={{ fontSize: 34 }} aria-hidden>📁</div>
          <div className="t-title mt-sm">Choose Folder</div>
          <div className="t-caption-sm muted mt-sm">Pick a folder — we'll process every invoice in it</div>
          <button className="btn btn-secondary mt-lg">Choose Folder</button>
        </div>
      </div>
    </div>
  );
}

function ConfirmView({ files, validCount, invalidCount, onCancel, onStart }) {
  return (
    <div>
      <h1 className="t-lg page-title">Upload invoices</h1>
      <p className="page-sub">
        <strong>{files.length} file{files.length > 1 ? "s" : ""} selected</strong>
      </p>
      <div className="card">
        <div className="pane-body" style={{ paddingTop: 8 }}>
          {files.map((f) => (
            <div className="between" style={{ padding: "9px 4px", borderBottom: "1px solid var(--hairline-soft)" }} key={f.id}>
              <div className="row" style={{ gap: 10, minWidth: 0 }}>
                <span style={{ color: f.valid ? "var(--emerald)" : "var(--amber-bright)" }}>{f.valid ? "✓" : "⚠"}</span>
                <span className="truncate">{f.file.name}</span>
              </div>
              {!f.valid && <span className="t-caption-sm muted" style={{ textAlign: "right" }}>{f.reason}</span>}
            </div>
          ))}
        </div>
        <div className="between" style={{ padding: "14px 20px", borderTop: "1px solid var(--hairline)" }}>
          <div className="t-caption-sm muted">
            {validCount} valid file{validCount > 1 ? "s" : ""}
            {invalidCount > 0 && <span style={{ color: "var(--amber)" }}> · {invalidCount} invalid</span>}
          </div>
          <div className="spread">
            <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
            <button className="btn btn-primary" onClick={onStart} disabled={validCount === 0}>
              Start Processing
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProcessingView({ files, results, done, total }) {
  const step = Math.min(total, done);
  const bars = files.filter((f) => f.valid);
  return (
    <div>
      <h1 className="t-lg page-title">Processing invoices</h1>
      <p className="page-sub">{total} invoice{total > 1 ? "s" : ""}</p>
      <div className="card">
        <div className="pane-body">
          {bars.length === 0 && <div className="empty-state">No valid files to process.</div>}
          {bars.map((f) => {
            const r = results[f.id] || { state: "waiting" };
            const label =
              r.state === "done"
                ? r.status === "REGISTERED" ? "Completed" : r.status === "NEEDS_REVIEW" ? "Needs review" : r.status === "REJECTED" || r.status === "FAILED" ? "Rejected" : "Completed"
                : r.state === "running" ? "Processing" : "Waiting";
            const icon =
              r.state === "done" ? (r.status === "REGISTERED" ? "✓" : r.status === "NEEDS_REVIEW" ? "⚠" : "✕") : r.state === "running" ? "⟳" : "·";
            return (
              <div className="between" style={{ padding: "9px 4px", borderBottom: "1px solid var(--hairline-soft)" }} key={f.id}>
                <div className="row" style={{ gap: 10, minWidth: 0 }}>
                  <span style={{ width: 18, textAlign: "center", color: r.state === "done" ? (r.status === "REGISTERED" ? "var(--emerald)" : r.status === "NEEDS_REVIEW" ? "var(--amber-bright)" : "var(--red)") : "var(--muted)" }}>
                    {icon}
                  </span>
                  <span className="truncate">{f.file.name}</span>
                </div>
                <span className="t-caption-sm muted nowrap">{label}</span>
              </div>
            );
          })}
        </div>
        <div className="between" style={{ padding: "14px 20px", borderTop: "1px solid var(--hairline)" }}>
          <span className="t-caption-sm muted">Processing {step} / {total}</span>
          <div style={{ width: 120, height: 6, background: "var(--surface-strong)", borderRadius: 99, overflow: "hidden" }}>
            <div style={{ width: `${total ? (step / total) * 100 : 0}%`, height: "100%", background: "var(--blue)", transition: "width 0.3s ease" }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryView({ counts, files, results }) {
  const bars = files.filter((f) => f.valid);
  const reviewList = bars.filter((f) => results[f.id]?.status === "NEEDS_REVIEW");
  return (
    <div>
      <div className="banner-success">
        <span style={{ width: 40, height: 40, borderRadius: "50%", background: "#fff", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 22, flex: "none" }}>✓</span>
        <div>
          <div className="t-title">Processing complete</div>
          <div className="t-caption-sm" style={{ color: "var(--emerald)" }}>{files.filter((f) => f.valid).length} invoices processed</div>
        </div>
      </div>

      <div className="summary-grid mb-lg">
        <SummaryCard accent="emerald" title="Registered" count={counts.REGISTERED} sub="自動登録されました" />
        <SummaryCard accent="amber" title="Need review" count={counts.NEEDS_REVIEW} sub="要確認" />
        <SummaryCard accent="red" title="Rejected" count={counts.REJECTED} sub="処理できませんでした" />
      </div>

      {counts.NEEDS_REVIEW > 0 ? (
        <div className="spread mb-lg">
          <Link href="/review">
            <button className="btn btn-primary">Review {counts.NEEDS_REVIEW} invoice{counts.NEEDS_REVIEW > 1 ? "s" : ""}</button>
          </Link>
        </div>
      ) : (
        <p className="t-caption-sm muted mb-lg">Nothing needs your attention — everything registered automatically.</p>
      )}

      <div className="card">
        <div className="pane-head"><span className="t-title">Results</span></div>
        <div className="pane-body" style={{ paddingTop: 8 }}>
          {bars.map((f) => {
            const r = results[f.id];
            return (
              <div className="between" style={{ padding: "10px 4px", borderBottom: "1px solid var(--hairline-soft)" }} key={f.id}>
                <div className="row" style={{ gap: 10, minWidth: 0 }}>
                  <span style={{ color: r?.status === "REGISTERED" ? "var(--emerald)" : r?.status === "NEEDS_REVIEW" ? "var(--amber-bright)" : "var(--red)" }}>
                    {r?.status === "REGISTERED" ? "✓" : r?.status === "NEEDS_REVIEW" ? "⚠" : "✕"}
                  </span>
                  <span className="truncate">{f.file.name}</span>
                </div>
                <span className="t-caption-sm muted nowrap" style={{ textAlign: "right", maxWidth: "55%" }}>
                  {r?.status === "REGISTERED" ? "Registered" : r?.status === "NEEDS_REVIEW" ? (r?.reason_codes?.length ? reasonsText(r.reason_codes).slice(0, 60) : "Needs review") : r?.note || "Rejected"}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="spread mt-lg">
        <Link href="/dashboard"><button className="btn btn-secondary">Back to Dashboard</button></Link>
        <Link href="/automate"><button className="btn btn-primary">Upload more invoices</button></Link>
      </div>
    </div>
  );
}