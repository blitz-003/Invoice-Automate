# Invoice Intake — UX/UI Specification

## 1. Product Concept

**Product name:** SAKANA AI

**Primary tagline:**
> Automating the boring office work.

**Japanese supporting tagline:**
> 請求書処理を、もっと簡単に。

The product is an internal business application for Japanese office workers that automates invoice intake and registration into an accounting system.

The UI should **not feel like an AI demo**.

It should feel like a reliable Japanese business application:

- Simple
- Calm
- Professional
- Trustworthy
- Minimal
- Easy to understand
- Suitable for middle-aged office workers

The user should not need to understand OCR, LLMs, agents, confidence scores, pipelines, or AI terminology.

### Core UX philosophy

> **One large action, four clear states, zero AI complexity.**

The employee should think:

> "I upload invoices → the system processes them → I only check the ones that need my attention."

---

# 2. Visual Design Direction

## Overall style

- White/minimal background
- Clean spacing
- Blue as the primary brand color
- Emerald as a secondary/action/success color
- Multiple shades of blue inspired by modern AI/technology branding
- Subtle borders
- Soft shadows only where useful
- Rounded cards, but not excessively rounded
- Professional Japanese SaaS aesthetic
- No excessive gradients
- No excessive illustrations
- No flashy AI animations
- No chatbot-style interface

The application should look trustworthy rather than futuristic.

## Color roles

### Blue

Primary navigation and primary actions.

Examples:

- Main buttons
- Active sidebar item
- Links
- Selected states
- Progress indicators

### Emerald

Success/positive states.

Examples:

- Registered
- Successfully processed
- Validation passed
- Success confirmation

### Amber/orange

Attention/review states.

Examples:

- Needs review
- Uncertain information
- Manual confirmation required

### Red

Error/rejection states.

Examples:

- Rejected
- Invalid document
- Registration failed
- Critical validation error

### Neutral gray

Used for:

- Secondary text
- Borders
- Disabled states
- Background sections
- Metadata

---

# 3. Application Structure

The overall application flow:

```text
LANDING
   │
   ▼
LOGIN
   │
   ▼
DASHBOARD
   │
   ├── AUTOMATE
   │      │
   │      ├── Select files
   │      ├── Select folder
   │      ├── Confirm files
   │      └── Processing
   │
   ├── PROCESSED
   │
   ├── PROCESSING
   │
   ├── REVIEW
   │
   ├── REJECTED
   │
   ├── SETTINGS
   │
   └── HELP
```

There should **not** be a primary sidebar item called "Delete".

Deletion is an action, not a workflow state.

Rejected documents can have delete actions from their details/history.

---

# 4. Landing Page

The landing page should be extremely simple.

### Content

```text
                    SAKANA AI

          Automating the boring office work.

             請求書処理を、もっと簡単に。

                  [ Login ]
```

The page should have:

- Product name/logo
- Tagline
- Short Japanese supporting line
- One clear Login button

Do not overload the landing page with:

- Pricing
- Features
- AI explanations
- Technical architecture
- Complex marketing sections
- Large illustrations
- Multiple CTA buttons

The goal is simply to enter the application.

---

# 5. Login

Keep login extremely simple.

Example:

```text
        SAKANA AI

        Login

        Email
        [________________]

        Password
        [________________]

        [ Login ]
```

The exact authentication implementation is separate from the UX specification.

---

# 6. Main Dashboard

After login, the user enters the dashboard.

## Layout

```text
┌──────────────────────────────────────────────────────────────┐
│ SAKANA AI                                      User / Profile │
├───────────────┬──────────────────────────────────────────────┤
│               │                                              │
│ + AUTOMATE    │ Dashboard                                    │
│               │                                              │
│ Dashboard     │ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│ Processed     │ │Processed │ │Processing│ │ Review   │       │
│ Processing    │ │    128   │ │     3    │ │     2    │       │
│ Review        │ └──────────┘ └──────────┘ └──────────┘       │
│ Rejected      │                                              │
│               │ ┌──────────┐                                  │
│ Settings      │ │ Rejected │                                  │
│ Help          │ │     1    │                                  │
│               │ └──────────┘                                  │
│               │                                              │
│               │ Upload invoices                               │
│               │                                              │
│               │ [ Choose Files ] [ Choose Folder ]            │
│               │                                              │
│               │ Recent invoices                               │
│               │ ────────────────────────────────────────────   │
│               │ ...                                          │
└───────────────┴──────────────────────────────────────────────┘
```

---

# 7. Sidebar

The sidebar should contain one visually dominant action:

```text
+ AUTOMATE
```

Then:

```text
Dashboard
Processed
Processing
Review
Rejected

────────────

Settings
Help
```

### Sidebar behavior

The active page should be clearly highlighted.

For example:

```text
▌ Review
```

with a blue active background or left border.

The `AUTOMATE` button should be visually stronger than normal navigation items.

---

# 8. Dashboard Summary Cards

The main dashboard should show four important states:

### Processed

Invoices successfully registered.

Example:

```text
Processed

128
Registered successfully
```

### Processing

Invoices currently being processed.

Example:

```text
Processing

3
Currently processing
```

### Review

Invoices requiring human attention.

Example:

```text
Review

2
Need your attention
```

This should be visually noticeable because it represents work the employee needs to perform.

### Rejected

Invoices that could not be processed.

Example:

```text
Rejected

1
Could not be processed
```

The exact numbers are dynamic.

---

# 9. Invoice Upload / Automate

The main automation action should be extremely obvious.

There should be two clear options:

```text
Choose invoices

[ Choose Files ]     [ Choose Folder ]
```

Do not combine these into an ambiguous single button.

The user can:

- Select one invoice
- Select multiple invoices
- Select a folder containing invoices

Supported files:

- PDF
- JPG
- JPEG
- PNG

---

# 10. Batch Upload Confirmation

If multiple files are selected, show a confirmation screen before processing.

Example:

```text
Upload invoices

8 files selected

─────────────────────────────────────────

✓ invoice_001.pdf
✓ invoice_002.pdf
✓ invoice_003.jpg
✓ invoice_004.pdf
⚠ invoice_005.txt
✓ invoice_006.pdf
✓ invoice_007.png
✓ invoice_008.pdf

─────────────────────────────────────────

7 valid files
1 invalid file

                    [ Cancel ] [ Start Processing ]
```

Invalid files should clearly explain why they cannot be processed.

Do not make the user manually inspect every successful file.

---

# 11. Batch Processing Screen

After the user starts processing, show a processing list.

Example:

```text
Processing invoices

8 invoices

────────────────────────────────────────────

invoice_001.pdf       ✓ Completed
invoice_002.pdf       ✓ Completed
invoice_003.jpg       ⚠ Needs review
invoice_004.pdf       ✓ Completed
invoice_005.pdf       ⟳ Processing
invoice_006.pdf       ✓ Completed
invoice_007.png       ⚠ Needs review
invoice_008.pdf       Waiting

────────────────────────────────────────────

Processing 5 / 8
```

Possible states:

- Waiting
- Processing
- Completed
- Needs review
- Rejected

Do not expose technical stages such as:

```text
PaddleOCR
LLM
Vision LLM
Schema validation
Pydantic
```

Instead use business-friendly stages where useful:

```text
ファイル確認
画像確認
文字読み取り
内容確認
会計システムへ登録
```

These stages can optionally appear when viewing a single processing item.

---

# 12. Processing Result Summary

When batch processing finishes, show a simple summary.

Example:

```text
Processing complete

8 invoices processed

┌────────────┐
│     5      │
│ Registered │
└────────────┘

┌────────────┐
│     2      │
│ Need review│
└────────────┘

┌────────────┐
│     1      │
│  Rejected  │
└────────────┘

             [ Review 2 invoices ]
```

Important UX principle:

**Do not force the user to review invoices that were successfully processed.**

If an invoice passed all automated checks, it should simply become registered.

Only invoices requiring attention should enter the human-review workflow.

---

# 13. Processed Page

The Processed page shows successfully registered invoices.

Example:

```text
Processed

Search invoices...
[________________________]

─────────────────────────────────────────────────────────────
Invoice No.     Supplier             Date          Amount
─────────────────────────────────────────────────────────────
YM-2026-0107    株式会社山田製作所     2026/01/07    ¥184,800
YM-2026-0108    東京フーズ株式会社     2026/01/08    ¥92,000
...
```

Status can be:

```text
Registered
登録済み
```

The user should be able to open an invoice to see its details.

---

# 14. Processing Page

The Processing page shows invoices that are still being processed.

Example:

```text
Processing

3 invoices currently processing

────────────────────────────────────────────

invoice_001.pdf       Processing...
invoice_002.pdf       Processing...
invoice_003.pdf       Waiting
```

The user should be able to open an item to see its processing progress.

---

# 15. Review Page

This is one of the **most important screens in the application**.

The Review page contains only invoices that need human attention.

Example:

```text
Review

2 invoices need your attention

────────────────────────────────────────────

⚠ invoice_003.pdf

Supplier:
株式会社山田製作所

Invoice:
YM-2026-0107

Amount:
¥184,800

Reason:
取引先を自動的に確認できませんでした。

                           [ Review ]

────────────────────────────────────────────

⚠ invoice_007.pdf

Supplier:
東京フーズ株式会社

Invoice:
YM-2026-0112

Amount:
¥92,000

Reason:
金額を確認してください。

                           [ Review ]
```

The review list should tell the user:

1. Which invoice needs attention
2. What information was detected
3. Why it needs attention
4. How to open the review screen

---

# 16. Human Review Detail Screen

This is the core UX differentiator.

The screen should be split into two major areas:

```text
┌─────────────────────────────────────────────────────────────┐
│ Review invoice                                  [Approve]   │
├──────────────────────────────┬──────────────────────────────┤
│                              │                              │
│ INVOICE DATA                 │ DOCUMENT                     │
│                              │                              │
│ Supplier                     │                              │
│ [株式会社山田製作所       ]   │       Invoice PDF/Image      │
│                              │                              │
│ Invoice Number               │                              │
│ [YM-2026-0107             ]   │                              │
│                              │                              │
│ Issue Date                   │                              │
│ [2026-01-07               ]   │                              │
│                              │                              │
│ Due Date                     │                              │
│ [2026-02-28               ]   │                              │
│                              │                              │
│ Line Items                   │                              │
│ ┌──────────────────────────┐ │                              │
│ │ Description | Qty | ... │ │                              │
│ │ Product A   | 120 | ... │ │                              │
│ │ Product B   |  10 | ... │ │                              │
│ └──────────────────────────┘ │                              │
│                              │                              │
│ Subtotal                     │                              │
│ [¥168,000                 ]   │                              │
│                              │                              │
│ Tax                          │                              │
│ [¥16,800                  ]   │                              │
│                              │                              │
│ Total                        │                              │
│ [¥184,800                 ]   │                              │
│                              │                              │
│ [ Reject ] [ Save ]          │                              │
│                  [ Register ]│                              │
└──────────────────────────────┴──────────────────────────────┘
```

---

# 17. Left Side — Editable Invoice Form

The left side contains the structured invoice data.

Fields include:

### Supplier

```text
Supplier
[ 株式会社山田製作所 ]
```

### Invoice number

```text
Invoice Number
[ YM-2026-0107 ]
```

### Issue date

```text
Issue Date
[ 2026-01-07 ]
```

### Due date

```text
Due Date
[ 2026-02-28 ]
```

### Currency

```text
Currency
[ JPY ]
```

### Line items

Line items should use a table.

```text
┌─────────────────────────────────────────────────────────────┐
│ Description │ Qty │ Unit │ Unit Price │ Amount │ Tax       │
├─────────────────────────────────────────────────────────────┤
│ Product A   │ 120 │ pcs  │ ¥1,250     │ ¥150,000│ 10%      │
│ Product B   │ 10  │ pcs  │ ¥1,800     │ ¥18,000 │ 10%      │
└─────────────────────────────────────────────────────────────┘
```

### Totals

```text
Subtotal
[ ¥168,000 ]

Tax
[ ¥16,800 ]

Total
[ ¥184,800 ]
```

The fields must be editable.

---

# 18. Right Side — Document Viewer

The right side shows the original invoice.

The user should be able to inspect the source document directly.

Required capabilities:

### Zoom

```text
[ − ]   100%   [ + ]
```

### Additional controls

Ideally:

```text
Fit to screen
Fullscreen
Rotate
```

The document should support:

- Zoom in
- Zoom out
- Mouse-wheel zoom
- Click-and-drag panning
- Fit to screen
- Fullscreen viewing

For PDFs, support page navigation if there are multiple pages.

Example:

```text
Page 1 / 3

[ Previous ] [ Next ]
```

---

# 19. Field ↔ Document Highlighting

This should be a major UX feature.

The structured field and original document should be connected.

For example:

If the user clicks:

```text
Total
[ ¥184,800 ]
```

the document viewer should:

1. Move to the relevant area
2. Zoom if necessary
3. Highlight the source value

Example:

```text
┌──────────────────────────────┐
│                              │
│ Subtotal      ¥168,000       │
│ Tax            ¥16,800       │
│                              │
│ TOTAL       [¥184,800]       │ ← highlighted
│                              │
└──────────────────────────────┘
```

Likewise, if the user clicks the highlighted amount inside the document, the corresponding `Total` field on the left should become focused.

This creates:

```text
Structured Data  ↔  Source Document
```

and helps the user trust the extraction.

---

# 20. Highlight Behavior

Do not highlight every extracted field simultaneously.

That would make the document visually noisy.

Instead:

### Default

No or very subtle highlights.

### Hover field

Temporarily show the corresponding document region.

### Click field

Keep the corresponding region highlighted and zoomed.

### Click document region

Focus the corresponding field.

This should feel natural and lightweight.

---

# 21. Line Item Highlighting

The same synchronization should apply to line items.

Example:

User clicks:

```text
Product A
Qty: 120
Amount: ¥150,000
```

The document automatically moves to the corresponding invoice line and highlights it.

This is particularly useful for invoices with many line items.

---

# 22. Review Reason

At the top of the review screen, clearly explain why the invoice requires human attention.

Example:

```text
⚠ 確認が必要です

取引先を自動的に確認できませんでした。
候補を確認してください。
```

Other examples:

```text
⚠ 金額を確認してください

請求書内の金額と計算結果が一致しません。
```

```text
⚠ 請求書番号を確認してください

請求書番号を正確に読み取れませんでした。
```

```text
⚠ 画像を確認してください

画像の一部が不鮮明です。
```

The UI should explain the problem in **human/business language**, not technical language.

Do not prominently display:

```text
confidence = 0.72
OCR confidence = 0.61
LLM score = 0.84
```

The system can use confidence internally, but the employee mainly needs to know:

> **What do I need to check?**

---

# 23. Suggested Values / Uncertain Fields

When the system is uncertain, it can provide a detected value or candidate.

Example:

```text
Supplier

Detected:
[ 山田製作所 ]

Possible match:
○ 株式会社山田製作所
○ 有限会社佐藤商店

                    [ Confirm ]
```

This minimizes manual typing.

The user should only correct the information that actually needs correction.

---

# 24. Review Actions

At the bottom or top-right of the review page:

```text
[ Reject ]     [ Save ]     [ Register ]
```

The primary action should be:

```text
[ Register ]
```

or:

```text
[ ✓ Register Invoice ]
```

Before final registration, show a confirmation:

```text
Register invoice?

This invoice will be registered in the accounting system.

Supplier:
株式会社山田製作所

Invoice:
YM-2026-0107

Total:
¥184,800

[ Cancel ]       [ Register ]
```

---

# 25. Successful Registration

After registration:

```text
✓ Registration complete

The invoice has been successfully registered.

Invoice:
YM-2026-0107

Amount:
¥184,800

Status:
登録済み

[ Back to Review ]
[ View Processed Invoices ]
[ Dashboard ]
```

The user should receive a clear success state.

---

# 26. Rejection

If an invoice cannot be processed or is intentionally rejected:

```text
Reject invoice

Reason

[____________________________]

[ Cancel ]       [ Reject Invoice ]
```

Rejected invoices appear under:

```text
Rejected
```

Deletion is an action from there rather than a top-level navigation category.

---

# 27. Rejected Page

Example:

```text
Rejected

─────────────────────────────────────────────────────────────

invoice_009.pdf

Reason:
Invalid document / unreadable image

Date:
2026/09/12

                         [ View ] [ Delete ]
```

The user can inspect why it was rejected.

---

# 28. Important UX State Model

The UI should reflect these business states:

```text
WAITING
   ↓
PROCESSING
   ↓
 ┌───────────────┬─────────────────┬───────────────┐
 ▼               ▼                 ▼
REGISTERED     NEEDS_REVIEW       REJECTED
                   │
                   ▼
             HUMAN CORRECTION
                   │
                   ▼
               REGISTERED
```

The important principle is:

> **Only invoices that require human intervention enter Review.**

---

# 29. Multiple Invoice UX

For multiple invoices:

```text
User selects folder
        ↓
System finds 20 invoices
        ↓
Process all automatically
        ↓
Results:
  15 Registered
   3 Review
   2 Rejected
        ↓
User reviews only the 3
```

Do not make the user open 20 invoices individually.

The batch workflow should maximize automation.

---

# 30. Notifications / Status Indicators

Use clear status badges.

Examples:

### Success

```text
✓ Registered
```

### Processing

```text
⟳ Processing
```

### Review

```text
⚠ Needs review
```

### Rejected

```text
✕ Rejected
```

Avoid complicated technical statuses.

---

# 31. Responsive Behavior

The primary target is desktop because invoice processing is an office workflow.

Desktop should use:

```text
Sidebar + Main Content
```

The review page should prioritize the two-column layout:

```text
┌───────────────┬─────────────────────┐
│ Invoice Form  │ Document Viewer     │
│               │                     │
│               │                     │
└───────────────┴─────────────────────┘
```

On smaller screens, the document viewer can move below the form rather than trying to maintain a cramped two-column layout.

---

# 32. What NOT to Expose in the UI

The user should not normally see technical implementation details such as:

- PaddleOCR
- OCR confidence
- Vision LLM
- Extraction LLM
- LangChain
- LangGraph
- Pydantic
- Vector database
- Prompt
- Agent
- Model name
- API endpoint
- Tool call
- Pipeline stage names

These belong to engineering/observability, not the employee-facing UX.

Instead:

```text
OCR unreliable
```

becomes:

```text
画像から文字を正確に読み取れませんでした。
```

And:

```text
PartnerResolver failed
```

becomes:

```text
取引先を確認できませんでした。
```

---

# 33. Core UX Principle for Human Review

The review experience should answer three questions immediately:

### 1. What is wrong?

```text
⚠ 取引先を確認してください
```

### 2. What did the system detect?

```text
株式会社山田製作所
```

### 3. Where did that information come from?

The document viewer highlights the source location.

Therefore:

```text
             HUMAN REVIEW

   What?          Detected?          Source?

   Problem   →    Value        ↔     Document
```

This is the core trust mechanism of the application.

---

# 34. Final Navigation

The final navigation should approximately be:

```text
SAKANA AI

┌──────────────────────┐
│ + AUTOMATE           │
├──────────────────────┤
│ Dashboard            │
│ Processed            │
│ Processing           │
│ Review               │
│ Rejected             │
│                      │
│ Settings             │
│ Help                 │
└──────────────────────┘
```

Main workflow:

```text
Dashboard
    │
    └── + AUTOMATE
            │
            ├── Choose Files
            └── Choose Folder
                    │
                    ▼
              Confirm Upload
                    │
                    ▼
               Processing
                    │
                    ▼
             Result Summary
              /      |      \
             /       |       \
            ▼        ▼        ▼
       Processed   Review   Rejected
                     │
                     ▼
               Review List
                     │
                     ▼
              Review Detail
              ┌──────┴──────┐
              │             │
        Editable Data    Document
              │             │
              └──────↔──────┘
                     │
                     ▼
                  Register
                     │
                     ▼
                Processed
```

# 35. Most Important Screens to Implement First

Priority order:

### P0 — Must have

1. Login
2. Dashboard
3. Upload / Automate
4. Batch upload confirmation
5. Processing list
6. Processing result summary
7. Review list
8. Review detail
9. Document viewer
10. Editable invoice form
11. Register confirmation
12. Success state

### P1 — Important

13. Processed page
14. Rejected page
15. Invoice detail
16. Search/filter
17. PDF page navigation
18. Zoom / pan / fullscreen
19. Field-to-document highlighting

### P2 — Nice to have

20. Settings
21. Help
22. Advanced filtering
23. Additional document controls

---

# 36. Overall Product Experience

The final experience should feel like:

```text
             SAKANA AI

        Upload invoices
              ↓
       System does the work
              ↓
     ┌────────┴────────┐
     ↓                 ↓
  Automatic          Human
  registration       review
     ↓                 ↓
     └────────┬────────┘
              ↓
        Accounting API
```

The employee should spend their time only on exceptions.

**The system handles the boring work.  
The employee handles the uncertain work.**

The most important UI concept is therefore:

> **Structured invoice data on the left + synchronized source document on the right.**

This makes the automation transparent, easy to correct, and trustworthy without exposing the underlying AI complexity.