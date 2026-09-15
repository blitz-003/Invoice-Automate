"use client";

export default function SummaryCard({ accent, title, count, sub, onClick, children }) {
  const Tag = onClick ? "a" : "div";
  return (
    <Tag
      className="card card-pad summary-card card-hover"
      href={onClick}
      onClick={onClick ? undefined : undefined}
      style={{ cursor: onClick ? "pointer" : "default", display: "block", textDecoration: "none" }}
    >
      <span className={`accent accent-${accent}`} aria-hidden />
      <div className="t-caption muted" style={{ marginBottom: 6 }}>{title}</div>
      <div className="count">{count ?? "—"}</div>
      <div className="sub">{children || sub}</div>
    </Tag>
  );
}