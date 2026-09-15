import { badgeFor } from "../lib/status";

const ICON = { success: "✓", warning: "⚠", danger: "✕", info: "⟳", neutral: "" };

export default function StatusBadge({ status, showJp = false }) {
  const b = badgeFor(status);
  return (
    <span className={`badge badge-${b.tone}`}>
      <span aria-hidden>{ICON[b.tone] === "⟳" ? "⟳" : ICON[b.tone]}</span>
      {b.text}
      {showJp && <span style={{ opacity: 0.7 }}>（{b.jp}）</span>}
    </span>
  );
}