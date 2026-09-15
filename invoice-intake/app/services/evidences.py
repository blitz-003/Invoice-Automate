from __future__ import annotations

from dataclasses import dataclass, field as dc_field


@dataclass
class EvidenceRef:
    source_ref: str
    sf_oid: str = ""
    image_path: str = ""
    bounds: list[float] = dc_field(default_factory=list)


def _dict_ref(index: int, sf_oid: str, field_name: str) -> str:
    return f"sf_oid:{sf_oid} invoice_slines[{index}] field:{field_name}"


def evidence_for_fields(index: int, sf_oid: str, field_names: list[str]) -> dict[str, str]:
    return {f: _dict_ref(index, sf_oid, f) for f in field_names}


def evidence_for_item_rows(rows: list, sf_oid: str) -> dict[int, dict[str, str]]:
    return {
        i: {name: _dict_ref(i, sf_oid, name) for name in (row.keys() if isinstance(row, dict) else ())}
        for i, row in enumerate(rows)
    }


def image_bounds(
    token_matrix: list[list[object]],
    needle: str,
) -> list[float]:
    """Return the bounding box of the first OCR token containing the needle."""
    if not needle:
        return []
    target = needle.replace(" ", "")
    for tokens in token_matrix:
        for tok in tokens:
            text = getattr(tok, "text", "")
            if target and target in text.replace(" ", ""):
                return list(getattr(tok, "bbox", []))
    return []