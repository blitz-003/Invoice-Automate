async function request(path, init) {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail?.message ?? body.detail ?? body.message ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

export const api = {
  dashboard: () => request("/api/dashboard"),
  jobs: () => request("/api/jobs"),
  job: (id) => request(`/api/jobs/${id}`),
  jobDocument: (id) => request(`/api/jobs/${id}/document`),
  jobEvidence: (id) => request(`/api/jobs/${id}/evidence`),
  invoices: (status = "") => request(`/api/invoices${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  invoice: (id) => request(`/api/invoices/${id}`),
  deleteInvoice: (id) => request(`/api/invoices/${id}`, { method: "DELETE" }),
  deleteJob: (id) => request(`/api/jobs/${id}`, { method: "DELETE" }),
  stopJob: (id) => request(`/api/jobs/${id}/stop`, { method: "POST" }),
  reprocess: (jobId) => request(`/api/jobs/${jobId}/reprocess`, { method: "POST" }),
  reviewQueue: () => request("/api/review"),
  approveReview: (id, reviewer, comment) =>
    request(`/api/review/${id}/approve?reviewer=${encodeURIComponent(reviewer)}&comment=${encodeURIComponent(comment)}`, { method: "POST" }),
  rejectReview: (id, reviewer, comment) =>
    request(`/api/review/${id}/reject?reviewer=${encodeURIComponent(reviewer)}&comment=${encodeURIComponent(comment)}`, { method: "POST" }),
  editField: (invoiceId, field, value, reviewer, reason) =>
    request(`/api/invoices/${invoiceId}/fields/${field}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value, reviewer, reason }),
    }),
  patchLines: (invoiceId, lines, reviewer, reason) =>
    request(`/api/invoices/${invoiceId}/lines`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lines, reviewer, reason }),
    }),
  upload: async (file) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/intake", { method: "POST", body: form });
    if (!res.ok) throw new Error(`${res.status}: upload failed`);
    return res.json();
  },
};

export function useUser() {
  if (typeof window === "undefined") return { name: "", email: "", authed: false };
  try {
    const raw = localStorage.getItem("sakana.user");
    if (!raw) return { name: "", email: "", authed: false };
    return { ...JSON.parse(raw), authed: true };
  } catch {
    return { name: "", email: "", authed: false };
  }
}

export function setUser(email) {
  const name = (email || "").split("@")[0] || "Demo";
  localStorage.setItem("sakana.user", JSON.stringify({ email, name }));
}

export function clearUser() {
  localStorage.removeItem("sakana.user");
}