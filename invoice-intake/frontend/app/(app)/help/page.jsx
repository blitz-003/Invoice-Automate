import Link from "next/link";

const SECTIONS = [
  {
    title: "How does it work?",
    body: "You upload invoices (PDF, JPG, JPEG, PNG). SAKANA AI reads the document, extracts the invoice data, and registers it in the accounting system. You only look at the invoices that need a human check.",
  },
  {
    title: "What should I do on the Review page?",
    body: "For each invoice shown, compare the values on the left with the original document on the right. Fix anything that looks wrong, then press Register. Click any field to highlight where the value was read from.",
  },
  {
    title: "Why does an invoice need review?",
    body: "Usually because the supplier could not be matched automatically, an amount did not add up, or the image quality was low. The reason is always explained in Japanese at the top of the review screen.",
  },
  {
    title: "What happens to rejected invoices?",
    body: "Invoices that cannot be processed appear under Rejected, with the reason and the original file. You can view them or delete them from there.",
  },
  {
    title: "Supported files",
    body: "PDF (including scanned pages) and images JPG, JPEG, PNG. Files up to 20MB, one invoice per file.",
  },
];

export default function HelpPage() {
  return (
    <div style={{ maxWidth: 680 }}>
      <h1 className="t-lg page-title">Help</h1>
      <p className="page-sub">ヘルプ — quick answers</p>

      {SECTIONS.map((s) => (
        <div className="card card-pad mb-md" key={s.title}>
          <h3 className="t-title mb-sm">{s.title}</h3>
          <p className="t-body-sm muted" style={{ margin: 0 }}>{s.body}</p>
        </div>
      ))}

      <div className="card card-pad" style={{ background: "var(--surface-soft)" }}>
        <p className="t-caption-sm muted" style={{ margin: 0 }}>
          Still stuck? Ask a colleague, or start an upload and see what the system finds —{" "}
          <Link href="/automate">Automate →</Link>
        </p>
      </div>
    </div>
  );
}