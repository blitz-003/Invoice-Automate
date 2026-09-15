"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { setUser, useUser } from "../../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const user = useUser();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (user.authed) router.replace("/dashboard");
  }, [user.authed, router]);

  const submit = (e) => {
    e.preventDefault();
    if (!email.trim()) {
      setError("Email is required.");
      return;
    }
    setUser(email.trim());
    router.replace("/dashboard");
  };

  return (
    <div
      className="landing"
      style={{ justifyContent: "center", minHeight: "100vh" }}
    >
      <div className="login-card">
        <div className="brand">
          <div className="mark">S</div>
          <span>
            <div className="name">SAKANA AI</div>
            <div className="jp">請求書処理を、もっと簡単に。</div>
          </span>
        </div>
        <form onSubmit={submit}>
          <h2 className="t-lg mb-lg">Login</h2>
          {error && (
            <div
              className="notice"
              style={{
                color: "var(--red)",
                background: "var(--red-soft)",
                borderColor: "#f5c6c6",
              }}
            >
              {error}
            </div>
          )}
          <div className="field">
            <label className="label" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              className="input"
              type="email"
              placeholder="you@company.jp"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
            />
          </div>
          <div className="field">
            <label className="label" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              className="input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          <button className="btn btn-primary btn-full mt-md" type="submit">
            Login
          </button>
          <p
            className="t-caption-sm muted mt-md"
            style={{ textAlign: "center" }}
          >
            Demo — enter any email to continue.
          </p>
          <p style={{ textAlign: "center", marginTop: 14 }}>
            <Link href="/" className="t-caption-sm muted">
              ← Back
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
