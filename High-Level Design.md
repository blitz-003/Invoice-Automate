# High-Level Design (HLD)

**Project:** Automated Invoice Intake System  
**Version:** 1.0  
**Date:** 2026-09-15

---

# 1. Purpose

This document describes the high-level architecture of the Automated Invoice Intake System.

The system receives invoice PDFs/images, extracts invoice information using OCR and LLM-based extraction, validates the extracted information using deterministic rules, detects duplicates, and registers valid invoices with the existing accounting system.

The design prioritizes:

1. Correctness over maximum automation
2. Deterministic validation wherever possible
3. Low-cost extraction
4. Human review for uncertain cases
5. Safe integration with the existing accounting API
6. Ability to scale beyond the 12 sample invoices

---

# 2. Architecture Overview

The proposed architecture is:

```text
                         ┌──────────────────────┐
                         │      User / UI       │
                         │ Upload Invoice(s)    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     API / Backend    │
                         │   Upload Endpoint    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   File Validation    │
                         │ Type / Size / Read   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Document Processing  │
                         │ PDF → Images        │
                         │ Image normalization │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Image Quality Check  │
                         │ Blur / Resolution    │
                         │ Contrast / Skew      │
                         │ Document Detection   │
                         └──────────┬───────────┘
                                    │
                         ┌──────────┴──────────┐
                         │                     │
                       Invalid                Valid
                         │                     │
                         ▼                     ▼
                      Reject            Preprocessing
                                             │
                                             ▼
                                          PaddleOCR
                                             │
                                             ▼
                                      OCR Validation
                                             │
                              ┌──────────────┴──────────────┐
                              │                             │
                         OCR Reliable                 OCR Unreliable
                              │                             │
                              ▼                             ▼
                         Text LLM                    Vision LLM
                              │                             │
                              └──────────────┬──────────────┘
                                             ▼
                                    Structured Invoice JSON
                                             │
                                             ▼
                                    Schema Validation
                                             │
                                             ▼
                                    Business Validation
                                             │
                                             ▼
                                    Duplicate Detection
                                             │
                                             ▼
                                     Confidence Scoring
                                             │
                              ┌──────────────┴──────────────┐
                              │                             │
                            High                    Medium / Low
                              │                             │
                              ▼                             ▼
                       Accounting API                  Review Queue
                              │                             │
                              │                     ┌───────┴───────┐
                              │                     │               │
                              │                  Approve         Reject
                              │                     │               │
                              │                     ▼               ▼
                              │              Accounting API      Failed
                              │
                              ▼
                       Registered Invoice
```

---

# 3. Architectural Components

The system consists of the following major components:

```text
1. Client / UI
2. API Backend
3. File Validation Service
4. Document Processing Service
5. Image Quality Assessment
6. Preprocessing Service
7. OCR Service
8. OCR Validation Service
9. Extraction Service
10. Schema Validation
11. Business Validation
12. Duplicate Detection
13. Confidence / Routing Engine
14. Human Review
15. Accounting API Client
16. Persistence / Database
17. Queue / Worker infrastructure
18. Logging / Observability
```

For the 8-hour MVP, these do not need to be implemented as separate microservices.

They can initially be modules within a single Python application.

---

# 4. Component Responsibilities

## 4.1 Client / UI

Responsibilities:

- upload invoice
- display processing status
- display extracted data
- display validation errors
- display review-required invoices
- allow correction of extracted fields
- allow registration after review

For the MVP, a simple web interface or command-line interface is sufficient.

---

# 5. API Backend

The backend is the entry point into the application.

Example:

```text
POST /invoices/upload
GET  /invoices/{id}
GET  /invoices/{id}/status
POST /invoices/{id}/review
POST /invoices/{id}/register
```

Responsibilities:

- receive uploads
- validate request
- create processing record
- trigger invoice processing
- return processing status
- expose results

The backend should not perform expensive OCR/LLM operations directly inside the request handler in the production architecture.

---

# 6. File Validation

The file-validation component performs inexpensive checks first.

```text
Input
  ↓
File exists?
  ↓
Supported format?
  ↓
Readable?
  ↓
Size acceptable?
  ↓
Has pages/content?
```

If validation fails:

```text
REJECTED
```

This prevents unnecessary OCR/LLM costs.

---

# 7. Document Processing

This component converts different input formats into a common representation.

Example:

```text
PDF
 │
 ├── Text PDF
 │
 └── Scanned PDF
          │
          ▼
      Page Images

JPG / PNG
    │
    ▼
Image
```

The system should not assume that every PDF has usable text.

A PDF may contain:

```text
PDF
 ├── Embedded text
 └── Scanned image
```

The processing strategy should therefore depend on the document type.

---

# 8. Image Quality Assessment

The Image Quality Assessment component determines whether the input is usable and whether preprocessing is necessary.

Checks include:

```text
Blur
Resolution
Contrast
Brightness
Noise
Skew
Document boundaries
```

Example output:

```json
{
  "document_detected": true,
  "resolution_ok": true,
  "blur_score": 220,
  "contrast_score": 0.82,
  "skew_angle": 1.2,
  "needs_preprocessing": false
}
```

The important design principle is:

```text
Quality assessment ≠ preprocessing
```

The system first decides whether preprocessing is necessary.

---

# 9. Preprocessing Service

Preprocessing is conditional.

Possible operations:

```text
Resize
Grayscale
Denoise
Contrast enhancement
Sharpen
Thresholding
Deskew
```

Architecture:

```text
Image
  │
  ▼
Quality Assessment
  │
  ├── Good ──────────────┐
  │                      │
  └── Needs improvement  │
           │             │
           ▼             │
      Preprocessing      │
           │             │
           └──────┬──────┘
                  ▼
                 OCR
```

The original image should be retained.

This is important because preprocessing can sometimes make OCR worse.

---

# 10. OCR Service

## Technology

**PaddleOCR** is the initial OCR candidate.

Reasons:

- supports Japanese
- suitable for scanned documents
- provides OCR confidence information
- can run locally
- avoids sending every document to a Vision LLM
- reduces cost
- keeps document processing more private

Output:

```json
{
  "text": "...",
  "blocks": [
    {
      "text": "請求書番号",
      "confidence": 0.98,
      "bbox": [100, 200, 300, 240]
    }
  ]
}
```

The bounding boxes are useful later for highlighting extracted fields in the UI.

---

# 11. OCR Validation

OCR output is not automatically trusted.

The validation component checks:

```text
OCR confidence
Text length
Expected invoice terminology
Date-like values
Numeric values
Supplier information
Garbage-text ratio
```

Example:

```text
OCR result
     │
     ▼
OCR Validation
     │
     ├── Reliable ──→ Text Extraction
     │
     └── Unreliable → Vision Extraction
```

This is an important cost optimization.

---

# 12. Extraction Service

The extraction service converts unstructured information into the required invoice schema.

There are two paths.

## Path A — Text Extraction

Used when OCR is sufficiently reliable.

```text
Invoice Image
      ↓
PaddleOCR
      ↓
OCR Text
      ↓
Text LLM
      ↓
Structured JSON
```

## Path B — Vision Extraction

Used when OCR is unreliable.

```text
Invoice Image
      ↓
Vision LLM
      ↓
Structured JSON
```

This gives the system a fallback for:

- handwriting
- unusual layouts
- poor OCR
- handwritten corrections
- complex visual structure

---

# 13. Why Not Use Vision LLM for Everything?

The architecture deliberately avoids:

```text
Every invoice
     ↓
Vision LLM
```

because that would unnecessarily increase:

- cost
- latency
- external API dependency
- privacy exposure

Instead:

```text
Good OCR
   ↓
Cheap text extraction

Bad OCR
   ↓
Vision LLM
```

This makes the system cost-aware.

---

# 14. Structured Output

The LLM should return structured data rather than free-form text.

Example:

```json
{
  "supplier_name": "東京フーズ株式会社",
  "invoice_number": "INV-2026-0107",
  "issue_date": "2026-01-07",
  "due_date": "2026-02-28",
  "currency": "JPY",
  "lines": [
    {
      "description": "商品A",
      "quantity": 10,
      "unit": "pcs",
      "unit_price": 1000,
      "amount": 10000
    }
  ],
  "subtotal": 10000,
  "tax_amount": 1000,
  "total_amount": 11000
}
```

The LLM should not be responsible for deciding whether the information is ultimately valid.

---

# 15. Schema Validation

The extracted JSON passes through deterministic schema validation.

Example:

```text
LLM Output
    ↓
Schema Validator
    │
    ├── Valid
    │
    └── Invalid
           ↓
       Review / Retry
```

Checks include:

```text
Required fields
Correct data types
Date format
Integer amounts
Valid line-item structure
```

A malformed LLM response must never directly reach the accounting API.

---

# 16. Business Validation

After schema validation, deterministic business rules are applied.

Examples:

### Date

```text
due_date >= issue_date
```

### Subtotal

```text
subtotal = Σ line.amount
```

### Tax

```text
tax = tax calculation according to tax code
```

### Total

```text
total = subtotal + tax
```

### Supplier

```text
supplier → accounting partner
```

This layer is particularly important because the accounting API itself recalculates amounts.

---

# 17. Partner Matching

The system retrieves:

```text
GET /partners
```

and maintains the partner master during processing.

Example:

```text
Invoice:
東京フーズ

Partner master:

P-1003
東京フーズ株式会社
alias: 東京フーズ
```

Result:

```text
partner_code = P-1003
```

Matching should use deterministic matching first.

Possible strategy:

```text
Exact name
    ↓
Exact alias
    ↓
Normalized name
    ↓
Fuzzy/LLM-assisted matching
    ↓
Human review
```

An uncertain supplier should not be automatically registered.

---

# 18. Tax Mapping

The system retrieves:

```text
GET /tax-codes
```

and maps extracted tax information to the accounting system's tax code.

Example:

```text
Invoice says:
10%

        ↓

Accounting code:
T10
```

The LLM should not invent arbitrary tax codes.

Only valid accounting-system codes should be submitted.

---

# 19. Duplicate Detection

Duplicate detection occurs before the accounting API.

Two levels are recommended.

## Level 1 — Document Hash

```text
SHA-256(file)
```

Detects:

```text
same file uploaded twice
```

## Level 2 — Business Duplicate

```text
partner_code + invoice_number
```

Detects:

```text
same invoice registered again
```

The accounting API provides another final protection through:

```text
DUPLICATE_INVOICE
```

Therefore:

```text
Application duplicate check
          ↓
Accounting API duplicate check
```

---

# 20. Confidence and Routing Engine

The routing engine determines whether an invoice can be automatically registered.

Example:

```text
                Confidence
                    │
          ┌─────────┼─────────┐
          │         │         │
         High     Medium      Low
          │         │         │
          ▼         ▼         ▼
       Register   Review     Review
```

Confidence should consider more than the LLM's self-reported confidence.

Inputs may include:

```text
OCR confidence
Required-field completeness
Supplier match confidence
Amount consistency
Date validation
Tax validation
Extraction consistency
```

---

# 21. Human Review

The review component handles invoices that cannot be safely automated.

Example UI:

```text
┌──────────────────────────────────────────────┐
│ Invoice Review                               │
├─────────────────────┬────────────────────────┤
│ Invoice Image       │ Extracted Data         │
│                     │                        │
│   [invoice]         │ Supplier: 東京フーズ   │
│                     │ Invoice: INV-1001      │
│                     │ Date: 2026-01-07       │
│                     │ Total: ¥184,800        │
│                     │                        │
│                     │ [Edit]                 │
└─────────────────────┴────────────────────────┘

        [Approve]       [Reject]
```

A useful future enhancement is field-level highlighting using OCR bounding boxes.

---

# 22. Accounting API Client

The accounting API should be isolated behind a dedicated client module.

Example:

```text
Application
     │
     ▼
AccountingClient
     │
     ├── get_partners()
     ├── get_tax_codes()
     ├── create_invoice()
     ├── list_invoices()
     └── delete_invoices()
            │
            ▼
     Accounting API
```

This prevents API-specific implementation details from spreading throughout the application.

---

# 23. Registration Flow

Final registration:

```text
Validated Invoice
       ↓
Duplicate Check
       ↓
Confidence Check
       ↓
AccountingClient
       ↓
POST /invoices
       ↓
┌──────────────┬────────────────┐
│              │                │
201            409              422/400
│              │                │
▼              ▼                ▼
Registered   Duplicate        Validation
                            /Business Error
```

Every response must be stored as a processing result.

---

# 24. Persistence

For the MVP, persistence can be lightweight.

Recommended conceptual data:

```text
InvoiceProcessing
------------------
id
file_hash
filename
status
ocr_path
extraction_path
extracted_data
validation_result
confidence
review_status
accounting_id
error
created_at
updated_at
```

For production, a relational database such as PostgreSQL would be appropriate.

---

# 25. Asynchronous Processing

The 8-hour MVP can process invoices synchronously.

Production architecture should use asynchronous processing.

```text
                  ┌──────────────┐
                  │     User     │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ API Workers  │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ Message Queue│
                  │ RabbitMQ/etc │
                  └──────┬───────┘
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
         Worker 1    Worker 2    Worker 3
             │           │           │
             ▼           ▼           ▼
           OCR/LLM     OCR/LLM     OCR/LLM
```

This allows:

- many users
- many invoices
- parallel processing
- API workers to remain responsive
- retrying failed jobs

---

# 26. MVP vs Production Architecture

## MVP

```text
User
 ↓
Python Application
 ↓
OCR
 ↓
LLM
 ↓
Validation
 ↓
Accounting API
```

Can run as one application.

---

## Production

```text
                 Load Balancer
                       │
                 ┌─────┴─────┐
                 ▼           ▼
             API Worker   API Worker
                 │           │
                 └─────┬─────┘
                       ▼
                  Message Queue
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      OCR Worker   LLM Worker   Validation Worker
          │            │            │
          └────────────┼────────────┘
                       ▼
                    Database
                       │
                       ▼
               Accounting API
```

---

# 27. Technology Choices

| Component | MVP Choice | Production Direction |
|---|---|---|
| Language | Python | Python |
| API | FastAPI | FastAPI |
| OCR | PaddleOCR | PaddleOCR / managed OCR |
| Text LLM | Low-cost LLM | Cost-optimized LLM routing |
| Vision | Vision LLM fallback | Vision model routing |
| Validation | Pydantic + Python | Pydantic + rules engine |
| Database | SQLite / PostgreSQL | PostgreSQL |
| Queue | Not required | RabbitMQ / Redis |
| Workers | Simple process | Celery/workers |
| Storage | Local | Object storage |
| Monitoring | Logging | OpenTelemetry + monitoring |
| LLM tracing | Optional | Langfuse/LangSmith |
| Deployment | Local | Docker/cloud |

---

# 28. LangChain / LangGraph Decision

These frameworks are **not required for the MVP**.

The core pipeline is mostly deterministic:

```text
OCR
 ↓
Validation
 ↓
Extraction
 ↓
Validation
 ↓
Accounting API
```

Raw Python is sufficient.

LangChain could be introduced if the project grows to require:

- standardized LLM integrations
- structured-output handling
- reusable prompt/model components
- retrieval
- tool calling

LangGraph becomes useful if the workflow becomes stateful and branching:

```text
OCR
 ↓
Validation
 ├── Retry OCR
 ├── Vision LLM
 ├── Human Review
 └── Continue
```

For an 8-hour take-home, adding these frameworks without a real need would increase complexity without improving the core solution.

---

# 29. Security Architecture

Invoice contents are untrusted.

```text
Invoice
   ↓
OCR
   ↓
UNTRUSTED DOCUMENT DATA
   ↓
LLM
```

The extraction prompt should clearly separate:

```text
SYSTEM INSTRUCTIONS
        +
DOCUMENT CONTENT
```

Document text must never be treated as an instruction.

API credentials should be supplied through environment variables.

Database queries must use parameterized queries.

---

# 30. Observability

Production should track each invoice through a trace:

```text
Invoice ID
   │
   ├── File validation
   ├── Quality assessment
   ├── Preprocessing
   ├── OCR
   ├── OCR validation
   ├── LLM extraction
   ├── Schema validation
   ├── Business validation
   ├── Duplicate check
   ├── Human review
   └── Accounting API
```

Useful metrics:

```text
processing_time
ocr_confidence
extraction_success_rate
review_rate
registration_success_rate
duplicate_rate
llm_tokens
llm_cost
api_error_rate
```

---

# 31. Failure Handling

The architecture treats failures differently depending on where they occur.

```text
File Failure
     ↓
Reject immediately

Image Quality Failure
     ↓
Reject / Request new upload

OCR Failure
     ↓
Vision LLM fallback

Extraction Failure
     ↓
Retry / Human Review

Schema Failure
     ↓
Retry / Human Review

Business Validation Failure
     ↓
Human Review

Duplicate
     ↓
Do Not Register

Accounting API Failure
     ↓
Retry if safe
     ↓
Otherwise Review
```

---

# 32. End-to-End Sequence

A typical successful invoice:

```text
User
 │
 │ upload invoice
 ▼
API
 │
 ▼
File Validation
 │
 ▼
Image Quality
 │
 ▼
Preprocessing
 │
 ▼
PaddleOCR
 │
 ▼
OCR Validation
 │
 │ good
 ▼
Text LLM
 │
 ▼
Structured JSON
 │
 ▼
Schema Validation
 │
 ▼
Business Validation
 │
 ▼
Duplicate Detection
 │
 ▼
Confidence Check
 │
 │ high
 ▼
Accounting API
 │
 ▼
201 Created
 │
 ▼
Registered
```

A difficult invoice:

```text
Invoice
   ↓
Quality Check
   ↓
Preprocessing
   ↓
OCR
   ↓
OCR confidence LOW
   ↓
Vision LLM
   ↓
Structured JSON
   ↓
Validation
   ↓
Supplier uncertain
   ↓
Human Review
   ↓
Correction
   ↓
Accounting API
   ↓
Registered
```

---

# 33. Example Failure Scenario

Suppose the LLM extracts:

```json
{
  "partner_name": "東京フーズ株式会社",
  "invoice_number": "INV-001",
  "subtotal": 168000,
  "tax_amount": 17000,
  "total_amount": 185000
}
```

The system should **not** immediately call the API.

It performs:

```text
subtotal = 168000
tax expected = 16800
total expected = 184800

LLM:
tax = 17000
total = 185000

        ↓

AMOUNT MISMATCH
        ↓
Human Review
```

This protects against an incorrect AI extraction.

---

# 34. Design Principles

The architecture follows these principles:

### 1. Cheap path first

```text
OCR → Text LLM
```

before:

```text
Vision LLM
```

when possible.

### 2. Validate before registering

```text
AI output ≠ trusted data
```

### 3. Deterministic rules over LLM reasoning

Use Python/business rules for:

```text
dates
amounts
tax
duplicates
API constraints
```

### 4. Fail safely

When uncertain:

```text
Human Review
```

rather than:

```text
Automatic Registration
```

### 5. Existing accounting system remains the source of truth

The application adapts to the accounting API rather than changing its contract.

---

# 35. Deployment Architecture

## MVP

```text
Developer Machine
│
├── Invoice Application
│
├── PaddleOCR
│
└── Accounting API
       localhost:8080
```

The application can be started with a single command.

---

## Production

```text
                    Internet
                       │
                       ▼
                Load Balancer
                       │
                 API Service
                       │
                 Message Queue
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Workers       Workers      Workers
          │            │            │
          └────────────┼────────────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
         PostgreSQL        Object Storage
             │
             ▼
       Accounting API
```

---

# 36. HLD Summary

The key architectural decision is to **separate extraction from trust**.

```text
                  EXTRACTION
                     │
             ┌───────┴────────┐
             │                │
           OCR            Vision LLM
             │                │
             └───────┬────────┘
                     ▼
              Structured Data
                     │
                     ▼
                 VALIDATION
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
      Schema       Business     Duplicate
     Validation    Rules        Detection
        │            │            │
        └────────────┼────────────┘
                     ▼
                 CONFIDENCE
                     │
              ┌──────┴──────┐
              ▼             ▼
          Automatic       Human
         Registration     Review
              │             │
              └──────┬──────┘
                     ▼
               Accounting API
```

The MVP should implement the **shortest reliable version** of this architecture rather than attempting the entire production architecture within the 8-hour constraint.