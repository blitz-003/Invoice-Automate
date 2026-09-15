from __future__ import annotations

import re
from typing import Any, Optional

import yaml

from app.models.input_errors import InputError, InputErrorKind
from app.schema.fast_rules import FastRulesTemplate

_YAML_BLOCK_RE = re.compile(r"```ya?ml\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]\.([A-Za-z_][A-Za-z0-9_]*)$")
_KEY_DOT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.(\d+)\.([A-Za-z_][A-Za-z0-9_]*)$")
_BLOCK_IDX_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]$")
_BLOCK_HEAD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", re.IGNORECASE)
_FIELD_KEY_RE = re.compile(r"^(\s+)([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")
_LIST_ITEM_RE = re.compile(r"^(\s+)-(?:\s+|$)(.*)$")


class ExtractedData:
    """Header values + item rows extracted from a source."""

    def __init__(
        self,
        header: Optional[dict[str, str]] = None,
        items: Optional[list[dict[str, str]]] = None,
        raw: str = "",
        source: str = "text",
    ):
        self.header: dict[str, str] = header or {}
        self.items: list[dict[str, str]] = items or []
        self.raw = raw
        self.source = source

    def copy(self) -> "ExtractedData":
        return ExtractedData(
            header=dict(self.header),
            items=[dict(r) for r in self.items],
            raw=self.raw,
            source=self.source,
        )


def build_prompt(schema: FastRulesTemplate, document_text: str) -> str:
    lines = [
        "You are an invoice data extraction engine. Return a YAML object only.",
        "",
        "Fields to extract (use these exact keys):",
    ]
    for block in schema.blocks:
        for field in block.fields:
            kind = "n rows" if block.rows_constant != 1 else "single value"
            req = "REQUIRED" if field.required else "optional"
            lines.append(f"- {block.name}.{field.name}\t({field.label or field.name}, {kind}, {req})")
    lines.append("")
    for block in schema.blocks:
        if block.rows_constant != 1:
            lines.append(
                f"Repeat {block.name}[n].FieldName for every line item, starting at 1."
            )
    lines.append("")
    lines.append("Rules:")
    lines.append("- Values must be plain strings (no units/currency symbols except where natural).")
    lines.append("- For dates use YYYY-MM-DD when possible.")
    lines.append("- For amounts keep digits and commas only (e.g. 1234567 or 1,234,567).")
    lines.append("- If a value is not present in the document, omit the key entirely.")
    lines.append("- Output only the YAML object, no commentary.")
    lines.append("")
    lines.append("DOCUMENT TEXT:")
    lines.append("<document>")
    lines.append(document_text or "(no text layer; not provided)")
    lines.append("</document>")
    return "\n".join(lines)


def _unwrap_flat_item_blocks(body: str, schema: FastRulesTemplate) -> str:
    """Reweight flat item blocks whose rows were collapsed via duplicate YAML keys.

    Some models emit line items as a single indented map with repeated keys::

        Item:
          Ord: "1"
          ItemName: A
          LineAmount: 67200
          Ord: "2"        # duplicate key; YAML keeps only the last value
          ItemName: B
          LineAmount: 36000

    PyYAML silently drops every occurrence but the final one, losing rows.
    This rewrites such a block into a proper YAML list-of-maps before parsing.
    """
    item_block = schema.item_block
    if item_block is None:
        return body
    block_name = item_block.name
    ordinal_field = item_block.ordinal_field

    lines = body.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        head = _BLOCK_HEAD_RE.match(line)
        if not head or head.group(1) != block_name:
            out.append(line)
            i += 1
            continue

        j = i + 1
        block: list[str] = []
        while j < len(lines):
            if _BLOCK_HEAD_RE.match(lines[j]) and not lines[j][0].isspace():
                break
            if not lines[j].strip():
                break
            block.append(lines[j])
            j += 1

        rewritten = _rewrite_flat_block(block, ordinal_field)
        if rewritten is None:
            out.append(line)
            i += 1
            continue
        out.append(f"{block_name}:")
        out.extend(rewritten)
        i = j
    return "\n".join(out)


def _rewrite_flat_block(block: list[str], ordinal_field: Optional[str]) -> Optional[list[str]]:
    """Return list-form lines for a flat repeated-key block, or None if not flat."""
    if not block or any(_LIST_ITEM_RE.match(b) for b in block):
        return None

    indent = None
    keys: list[str] = []
    for b in block:
        m = _FIELD_KEY_RE.match(b)
        if m is None:
            return None
        if indent is None:
            indent = m.group(1)
        elif len(m.group(1)) != len(indent):
            return None
        keys.append(m.group(2))

    repeated = sorted({k for k in keys if keys.count(k) > 1})
    if not repeated:
        return None
    row_key = ordinal_field if ordinal_field in repeated else repeated[0]
    indent_len = len(indent)
    close_indent = " " * indent_len

    rows: list[list[str]] = []
    current: list[str] = []
    for b in block:
        m = _FIELD_KEY_RE.match(b)
        if m.group(2) == row_key and current:
            rows.append(current)
            current = []
        raw_val = (m.group(3) or "").strip()
        if len(raw_val) >= 2 and raw_val[0] == raw_val[-1] and raw_val[0] in "\"'":
            raw_val = raw_val[1:-1]
        current.append(f"{m.group(2)}: \"{raw_val}\"")
    if current:
        rows.append(current)

    if len(rows) < 2:
        return None

    out_lines: list[str] = []
    for row in rows:
        out_lines.append(f"{close_indent}- {row[0]}")
        for item in row[1:]:
            out_lines.append(f"{close_indent}  {item}")
    return out_lines


def parse_llm_output(output: str, schema: FastRulesTemplate) -> ExtractedData:
    block = _YAML_BLOCK_RE.search(output)
    body = block.group(1) if block else _strip_fences(output)
    body = _unwrap_flat_item_blocks(body, schema)
    try:
        parsed = yaml.safe_load(body) or {}
    except yaml.YAMLError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    header: dict[str, str] = {}
    items: list[dict[str, str]] = []
    item_block_names = {b.name for b in schema.blocks if b.rows_constant != 1}
    for key, value in parsed.items():
        m = _KEY_RE.match(key) or _KEY_DOT_RE.match(key)
        if m:
            block_name, idx, field = m.groups()
            while len(items) < int(idx):
                items.append({})
            items[int(idx) - 1][field] = _to_text(value)
            continue
        mi = _BLOCK_IDX_RE.match(key)
        if mi and key and mi.group(1) in item_block_names:
            # Item[1]: {Ord: 1, ItemName: ...}
            block_name, idx = mi.groups()
            row = _item_row(value)
            if row:
                while len(items) < int(idx):
                    items.append({})
                items[int(idx) - 1].update(row)
            continue
        if key in item_block_names and isinstance(value, list):
            # Item:\n  - Ord: 1\n    ItemName: ...
            for row_value in value:
                row = _item_row(row_value)
                if row:
                    items.append(row)
            continue
        if isinstance(value, dict):
            # Nested header block: SellerInfo:\n  SellerName: ... -> SellerInfo.SellerName
            header.update({f"{key}.{k}": _to_text(v) for k, v in value.items()})
            continue
        if "." in key:
            block_name, field = key.split(".", 1)
            if block_name in {b.name for b in schema.blocks} and field:
                header[f"{block_name}.{field}"] = _to_text(value)
            else:
                header[key] = _to_text(value)
        else:
            # Bare top-level keys are tolerated and mapped as-is.
            header[key] = _to_text(value)
    items = [r for r in items if r]
    return ExtractedData(header=header, items=items, raw=body)


def _item_row(value: Any) -> dict[str, str]:
    """Normalize a single item row from either a dict or a list of pairs."""
    if isinstance(value, dict):
        return {_to_text(k): _to_text(v) for k, v in value.items() if _to_text(v)}
    if isinstance(value, (list, tuple)):
        row: dict[str, str] = {}
        for pair in value:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                k, v = pair
                if _to_text(v):
                    row[_to_text(k)] = _to_text(v)
        return row
    return {}


def _strip_fences(output: str) -> str:
    lines = output.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def extraction_errors(schema: FastRulesTemplate, data: ExtractedData) -> list[InputError]:
    errors: list[InputError] = []
    if not data.header and not data.items:
        return [InputError(kind=InputErrorKind.NOT_AN_INVOICE,
                            message="The document did not yield any invoice fields.")]
    for block in schema.blocks:
        if block.rows_constant != 1:
            continue
        for field in block.fields:
            if field.required and not data.header.get(f"{block.name}.{field.name}"):
                errors.append(InputError(
                    kind=InputErrorKind.EXTRACTION_FAILED,
                    message=f"Required field {block.name}.{field.name} was not extracted.",
                ))
    return errors