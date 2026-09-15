export function fmtMoney(v, currency = "JPY") {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  const sym = currency === "JPY" ? "¥" : "";
  return `${sym}${n.toLocaleString("en-US")}`;
}

export function fmtDate(v) {
  if (!v) return "—";
  const s = String(v).slice(0, 10);
  return s.replace(/-/g, "/");
}

export function fmtDateTime(v) {
  if (!v) return "—";
  return String(v).slice(0, 16).replace("T", " ");
}

export function fmtPct(v) {
  if (v === null || v === undefined) return "—";
  return `${Math.round(Number(v) * 100)}%`;
}

export function jpy(v) {
  return fmtMoney(v, "JPY");
}