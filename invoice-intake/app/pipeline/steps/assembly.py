from __future__ import annotations

import json
from typing import Optional

from app.models.resolvers import ResolutionResult
from app.models.responses import FinalInvoice, OutputRow, ResolvedField
from app.pipeline.steps.resolution_stage import assemble_items
from app.schema.fast_rules import FastRulesTemplate
from app.services.extractor import ExtractedData


def build_final_invoice(
    schema: FastRulesTemplate,
    resolution: ResolutionResult,
    item_rows: list[dict[str, str]],
    job_key: str,
    *,
    sf_oid: str,
    ocr_oid: str,
    secondary: Optional[ExtractedData],
    log: list[str],
) -> tuple[FinalInvoice, list[OutputRow]]:
    invoice = FinalInvoice(job_key=job_key, source_id=sf_oid)
    rows: list[OutputRow] = []
    sanitized: dict[str, str] = {}
    resolved_fields: list[ResolvedField] = []

    for field_name, cleaned in sorted(resolution.cleaned.items()):
        sanitized[field_name] = cleaned.value
        resolved_fields.append(ResolvedField(
            name=field_name,
            value=cleaned.value,
            confidence=cleaned.confidence,
            verified=bool(cleaned.verified),
            error=cleaned.error.message if cleaned.error else None,
        ))

    for block in schema.blocks:
        if block.rows_constant == 1:
            fields: dict[str, str] = {}
            for f in block.fields:
                key = f"{block.name}.{f.name}"
                fields[f.name] = sanitized.get(key, "")
            rows.append(OutputRow(
                key=block.name,
                fields=fields,
                refs={fn: f"{sf_oid}|{block.name}.{fn}" for fn in fields},
            ))

    for i, row in enumerate(item_rows, start=1):
        display = {k: v for k, v in row.items() if k != "line_total"}
        rows.append(OutputRow(
            key=f"Item[{i}]",
            fields=display,
            refs={fn: f"{sf_oid}|Item[{i}].{fn}" for fn in display},
        ))

    aggregate_note = ""
    sanitized.setdefault("Aggregate.LineTotal", "")
    rows.append(OutputRow(
        key="Total",
        fields={"LineTotal": _line_total_of(item_rows), "TotalAmount": sanitized.get("Invoice.TotalAmount", "")},
        refs={},
    ))

    invoice.resolved_fields = resolved_fields
    invoice.output_rows = rows
    invoice.sanitized_values = sanitized
    invoice.reviewers = []
    invoice.all_instances = {
        "stage1_text": json.loads(json.dumps(resolution.cleaned, default=str)),
        "stage2_photo": secondary.raw if secondary else None,
        "ocr_source": ocr_oid,
    }
    invoice.external_ids = {"sf_oid": sf_oid, "ocr_oid": ocr_oid}
    log.append(f"assembly: {len(rows)} output rows · {len(resolved_fields)} resolved fields")
    return invoice, rows


def _line_total_of(item_rows: list[dict[str, str]]) -> str:
    from app.pipeline.steps.resolution_stage import _line_amount

    total = sum(_line_amount(row) for row in item_rows)
    if total.is_integer():
        return str(int(total))
    return f"{total:.2f}"