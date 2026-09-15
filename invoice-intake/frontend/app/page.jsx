import Link from "next/link";

export default function Landing() {
  return (
    <div className="landing">
      <div className="mark-xl" aria-hidden>
        S
      </div>
      <h1>SAKANA AI</h1>
      <p className="tagline">Automating the boring office work.</p>
      <p className="tagline-jp">請求書処理を、もっと簡単に。</p>
      <div className="mt-xl">
        <Link href="/login">
          <button className="btn btn-primary" style={{ padding: "14px 40px" }}>
            Login
          </button>
        </Link>
      </div>
    </div>
  );
}
