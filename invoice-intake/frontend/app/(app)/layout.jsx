"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api, useUser, clearUser } from "../../lib/api";

export default function AppLayout({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const user = useUser();
  const [counts, setCounts] = useState({ review: 0, rejected: 0, processing: 0 });
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    let alive = true;
    api.dashboard()
      .then((d) => {
        if (!alive) return;
        const st = d.invoice_status || {};
        setCounts({
          review: d.pending_review ?? 0,
          rejected: (st.REJECTED || 0) + (st.FAILED || 0),
          processing: (st.REGISTERING || 0) + (st.RECEIVED || 0),
        });
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const onPointerDown = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [menuOpen]);

  useEffect(() => setMenuOpen(false), [pathname]);

  const activeFor = (prefixes) =>
    prefixes.some((p) => pathname?.startsWith(p)) ? "active" : "";

  const logout = () => {
    clearUser();
    router.replace("/");
  };

  const listItem = (href, label, dot, count, prefixes) => (
    <Link href={href} className={`nav-item ${activeFor(prefixes)}`}>
      {dot && <span className={`dot dot-${dot}`} aria-hidden />}
      <span className="grow truncate">{label}</span>
      {count !== undefined && count > 0 && (
        <span
          className="badge"
          style={{
            background: dot === "rejected" ? "var(--red-soft)" : "var(--amber-soft)",
            color: dot === "rejected" ? "var(--red)" : "var(--amber)",
          }}
        >
          {count}
        </span>
      )}
    </Link>
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="mark" aria-hidden>S</span>
          <span>
            <div className="name">SAKANA AI</div>
            <div className="jp">請求書処理を、もっと簡単に。</div>
          </span>
        </div>

        <Link href="/automate" className="automate-btn">
          <span style={{ fontSize: 18, lineHeight: 1 }}>+</span>
          AUTOMATE
        </Link>

        <nav>
          {listItem("/dashboard", "Dashboard", null, undefined, ["/dashboard"])}
          {listItem("/processed", "Processed", null, undefined, ["/processed"])}
          {listItem("/processing", "Processing", null, counts.processing, ["/processing"])}
          {listItem("/review", "Review", "review", counts.review, ["/review"])}
          {listItem("/rejected", "Rejected", "rejected", counts.rejected, ["/rejected"])}
        </nav>
      </aside>

      <div className="main">
        <header className="topbar">
          <span className="t-title truncate">{pageTitle(pathname)}</span>
          <div className="topbar-right" ref={menuRef}>
            <button
              className="avatar-circle avatar-btn"
              onClick={() => setMenuOpen((o) => !o)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              title={user.email || "Account"}
            >
              {(user.name || "U").slice(0, 1).toUpperCase()}
            </button>
            {menuOpen && (
              <div className="user-menu" role="menu">
                <div className="user-menu-head">
                  <div className="t-caption-sm" style={{ fontWeight: 600 }}>{user.name || "User"}</div>
                  <div className="t-caption-sm muted" style={{ wordBreak: "break-word" }}>{user.email || ""}</div>
                </div>
                <Link href="/settings" className="user-menu-item" role="menuitem">Settings</Link>
                <Link href="/help" className="user-menu-item" role="menuitem">Help / Support</Link>
                <button className="user-menu-item btn-plain" role="menuitem" onClick={logout}>Log out</button>
              </div>
            )}
          </div>
        </header>
        <main className="page">{children}</main>
      </div>
    </div>
  );
}

function pageTitle(pathname) {
  if (pathname === "/dashboard") return "Dashboard";
  if (pathname === "/automate") return "Automate";
  if (pathname?.startsWith("/processed")) return "Processed invoices";
  if (pathname?.startsWith("/processing")) return "Processing";
  if (pathname?.startsWith("/review")) return "Review";
  if (pathname?.startsWith("/rejected")) return "Rejected";
  if (pathname?.startsWith("/settings")) return "Settings";
  if (pathname?.startsWith("/help")) return "Help";
  return "SAKANA AI";
}