"use client";

import { useState } from "react";

export default function SettingsPage() {
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({ language: "ja-en", autoReview: true, currency: "JPY" });

  const save = (e) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div style={{ maxWidth: 620 }}>
      <h1 className="t-lg page-title">Settings</h1>
      <p className="page-sub">Preferences for invoice processing · 設定</p>

      <form className="card card-pad" onSubmit={save}>
        <div className="field">
          <label className="label" htmlFor="language">Display language</label>
          <select id="language" className="input" value={form.language} onChange={(e) => setForm((f) => ({ ...f, language: e.target.value }))}>
            <option value="ja-en">日本語 primarily / English labels</option>
            <option value="en">English</option>
            <option value="ja">日本語</option>
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="currency">Default currency</label>
          <select id="currency" className="input" value={form.currency} onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value }))}>
            <option value="JPY">JPY (¥)</option>
            <option value="USD">USD ($)</option>
          </select>
        </div>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <div className="t-caption-sm">Automatically register clear invoices</div>
            <div className="t-caption-sm muted">Invoices that pass all checks are registered without review.</div>
          </div>
          <input
            type="checkbox"
            checked={form.autoReview}
            onChange={(e) => setForm((f) => ({ ...f, autoReview: e.target.checked }))}
            style={{ width: 20, height: 20, accentColor: "var(--blue)" }}
          />
        </div>
        <div className="spread mt-lg">
          <button className="btn btn-primary" type="submit">Save settings</button>
          {saved && <span className="badge badge-success">✓ Saved</span>}
        </div>
      </form>
    </div>
  );
}