from __future__ import annotations

from app.schema.fast_rules import FastRulesTemplate
from app.services.extractor import ExtractedData
from app.services.similarity import max_ngram_relation


def merge_extracts(
    primary: ExtractedData,
    secondary: ExtractedData | None,
    schema: FastRulesTemplate,
) -> ExtractedData:
    """Merge secondary (vision/photo) into primary (text), primary wins per field."""
    merged = primary.copy()
    if secondary is None:
        return merged

    for key, value in secondary.header.items():
        if key not in merged.header or not merged.header[key]:
            if value:
                merged.header[key] = value

    # Item rows: align by ordinal if present, else by item-name similarity.
    if not merged.items:
        merged.items = [dict(r) for r in secondary.items]
        merged.source = "text+vision"
        return merged

    for row in secondary.items:
        target = _find_target(merged.items, row, schema)
        if target is None:
            merged.items.append(row)
            continue
        for field, value in row.items():
            if not target.get(field):
                target[field] = value
    merged.source = "text+vision"
    return merged


def _find_target(rows: list[dict], row: dict, schema: FastRulesTemplate) -> dict | None:
    item_block = schema.item_block
    if item_block and item_block.ordinal_field:
        ord_a = row.get(item_block.ordinal_field, "")
        if ord_a:
            for target in rows:
                if str(target.get(item_block.ordinal_field, "")) == str(ord_a):
                    return target
    name_fields = [f.name for f in (item_block.fields if item_block else []) if "name" in f.name.lower()]
    for field in name_fields:
        a = row.get(field, "")
        if not a:
            continue
        best = None
        best_score = 0.0
        for target in rows:
            b = target.get(field, "")
            if not b:
                continue
            score = max_ngram_relation(3, a, b)
            if score > best_score:
                best_score = score
                best = target
        if best is not None and best_score >= 0.55:
            return best
    return None