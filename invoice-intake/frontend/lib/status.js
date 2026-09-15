export const FINAL_STATUSES = new Set(["REGISTERED", "NEEDS_REVIEW", "REJECTED", "FAILED", "DONE"]);

export const PROCESSING_STEPS = [
  "RECEIVED",
  "FILE_VALIDATED",
  "QUALITY_CHECKED",
  "PREPROCESSED",
  "OCR_COMPLETED",
  "OCR_VALIDATED",
  "EXTRACTING",
  "EXTRACTED",
  "SCHEMA_VALIDATED",
  "BUSINESS_VALIDATED",
  "DUPLICATE_CHECKED",
  "CONFIDENCE_SCORED",
];

export const BUSINESS_STEPS = ["ファイル確認", "画像確認", "文字読み取り", "内容確認", "会計システムへ登録"];

// business state (review / processing / rejected / registered)
export function businessState(status) {
  if (status === "REGISTERED") return "registered";
  if (status === "NEEDS_REVIEW") return "review";
  if (status === "REJECTED" || status === "FAILED") return "rejected";
  if (status === "PROCESSING" || status === "REGISTERING" || status === "RECEIVED") return "processing";
  if (!status) return "unknown";
  return "processing"; // any remaining intermediate job status
}

export function isProcessing(status) {
  return !FINAL_STATUSES.has(status);
}

export function badgeFor(status) {
  const s = businessState(status);
  if (s === "registered") return { tone: "success", text: "✓ Registered", jp: "登録済み" };
  if (s === "review") return { tone: "warning", text: "Need review", jp: "要確認" };
  if (s === "rejected") return { tone: "danger", text: "Rejected", jp: "処理不可" };
  if (s === "processing") return { tone: "info", text: "Processing", jp: "処理中" };
  return { tone: "neutral", text: status || "—", jp: "" };
}

export const REASON_TEXT = {
  PARTNER_NOT_FOUND: "取引先を自動的に確認できませんでした。取引先の候補を確認してください。",
  LOW_CONFIDENCE: "読み取りの信頼性が低い項目があります。内容を確認してください。",
  AMOUNT_MISMATCH: "請求書内の金額と計算結果が一致しません。金額を確認してください。",
  INVALID_DATE: "日付の読み取りを確認してください。",
  UNKNOWN_TAX_RATE: "税率の読み取りを確認してください。",
  INVALID_FILETYPE: "このファイル形式は対応していません。PDF・JPG・JPEG・PNGをご利用ください。",
  FILE_TOO_LARGE: "ファイルサイズが大きすぎます。20MB以下のファイルをご利用ください。",
  CORRUPTED_FILE: "ファイルが開けませんでした。ファイルが破損していないか確認してください。",
  EMPTY_FILE: "ファイルが空です。ファイルを確認してください。",
  DOCUMENT_NOT_DETECTED: "書類が正しく撮影されているか確認してください。",
  IMAGE_CUTOFF: "書類の一部が画像から切れています。全体が写るように撮影してください。",
  IMAGE_UNREADABLE: "画像から文字を正確に読み取れませんでした。",
  NOT_AN_INVOICE: "請求書として認識できませんでした。ファイルを確認してください。",
  SCHEMA_INVALID: "請求書の必須項目を読み取れませんでした。",
  UNABLE_TO_EXTRACT: "請求書の内容を確認できませんでした。",
  EXTRACTION_FAILED: "請求書の内容を確認できませんでした。",
  OCR_FAILED: "文字の読み取りに失敗しました。ファイルを再確認してください。",
  OCR_UNRELIABLE: "画像から文字を正確に読み取れませんでした。",
  HANDWRITING: "手書きの部分があるため、内容を確認してください。",
  VISION_EXTRACTION_UNCERTAIN: "文字の読み取り結果を確認してください。",
  DUPLICATE_FILE: "このファイルはすでに処理済みです。",
  DUPLICATE_INVOICE: "同じ番号の請求書がすでに登録されています。",
  ACCOUNTING_REJECTED: "会計システムへの登録に失敗しました。",
  INVALID_PDF: "PDFを読み取れませんでした。ファイルを確認してください。",
  UNSUPPORTED_FILE: "このファイル形式は対応していません。",
};

export function reasonText(code, fallback = "内容を確認してください。") {
  return REASON_TEXT[code] || fallback;
}

export function reasonsText(codes) {
  if (!codes || codes.length === 0) return "内容を確認してください。";
  return codes.map((c) => reasonText(c)).join(" ");
}