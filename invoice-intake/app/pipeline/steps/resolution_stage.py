from __future__ import annotations

import re
from typing import Optional

from app.models.resolvers import ResolutionContext, ResolutionResult
from app.schema.fast_rules import FastRulesTemplate
from app.services.extractor import ExtractedData
from app.services.resolvers import FieldResolver

_NUM_CLEAN = re.compile(r"[\d,]+(?:\.\d+)?")
_NUM_TYPED = {"Quantity", "UnitPrice", "LineAmount", "TaxTotal", "TotalAmount"}


def resolve(
    schema: FastRulesTemplate,
    data: ExtractedData,
    overrides: Optional[dict[str, str]] = None,
) -> ResolutionResult:
    context = ResolutionContext(input_values=data.header, overrides=overrides or {})
    return FieldResolver().resolve(schema, data.header, context)


def assemble_items(
    schema: FastRulesTemplate,
    data: ExtractedData,
    resolution: ResolutionResult,
    log: list[str],
) -> tuple[list[dict[str, str]], str, bool]:
    """Finalize item rows: ordinals, numeric cleaning, aggregation cross-check."""
    item_block = schema.item_block
    rows: list[dict[str, str]] = []
    for i, raw in enumerate(data.items, start=1):
        cleaned: dict[str, str] = {}
        for field in (item_block.fields if item_block else []):
            value = raw.get(field.name, "")
            if field.name in _NUM_TYPED:
                cleaned[field.name] = _clean_number(value)
            else:
                cleaned[field.name] = value.strip()
        if item_block and item_block.ordinal_field and not cleaned.get(item_block.ordinal_field):
            cleaned[item_block.ordinal_field] = str(len(rows) + 1)
        rows.append(cleaned)

    order = item_block.ordinal_field if item_block else None
    if order:
        try:
            rows.sort(key=lambda r: int(r.get(order, "0") or 0))
        except ValueError:
            pass
        for i, row in enumerate(rows, start=1):
            row[order] = str(i)

    total_clean = resolution.cleaned.get("Invoice.TotalAmount")
    total = None
    if total_clean and total_clean.is_number:
        total = total_clean.numeric_value

    line_total = 0.0
    for row in rows:
        line_total += _line_amount(row)
    if rows:
        rows[-1]["line_total"] = _fmt(line_total)

    from app.schema.fast_rules import aggregate_total_cross_check

    cross_ok = aggregate_total_cross_check(total, line_total if rows else None)
    note = ""
    if rows and total is not None and not cross_ok:
        note = (
            f"aggregation mismatch: line items sum {_fmt(line_total)} "
            f"vs reported total {_fmt(total)}"
        )
        log.append(f"post_condition: {note} (conflict anomaly kept for review)")
    else:
        log.append("post_condition: aggregate total cross-check truthful")
    return rows, note, cross_ok


def _line_amount(row: dict[str, str]) -> float:
    from app.schema.fast_rules import normalize_amount

    qty = normalize_amount(row.get("Quantity", "")) or 0.0
    unit = normalize_amount(row.get("UnitPrice", "")) or 0.0
    direct = normalize_amount(row.get("LineAmount", ""))
    if direct is not None:
        return direct
    return qty * unit


def _clean_number(value: str) -> str:
    text = value.replace("￥", "").replace("¥", "").replace("円", "").strip()
    m = _NUM_CLEAN.search(text)
    if not m:
        return ""
    num = m.group(0).replace(",", "")
    return str(float(num)) if "." in num else num


def _fmt(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}"