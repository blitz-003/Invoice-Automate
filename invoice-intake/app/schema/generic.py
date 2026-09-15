from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from app.schema.fast_rules import FastRulesTemplate, TemplateBlock
from app.utils.typed import make_typed_tuple

_INT_RE = re.compile(r"[-+]?\d+")
_FLOAT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _pytype(raw_type: str):
    if raw_type in ("int",):
        return make_int
    if raw_type in ("float", "number"):
        return make_float
    if raw_type == "str":
        return make_str
    return make_str


def make_str(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in ("none", "null", "n/a", "na"):
        return ""
    return s


def make_int(value: Any) -> int:
    if value is None:
        return 0
    text = str(value).replace(",", "")
    m = _INT_RE.search(text)
    return int(m.group(0)) if m else 0


def make_float(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).replace(",", "")
    m = _FLOAT_RE.search(text)
    return float(m.group(0)) if m else 0.0


def build_tuple_classes(schema: FastRulesTemplate) -> dict[str, type]:
    """Create one NamedTuple per block (values stay strings; typed parsing happens in rows)."""
    classes: dict[str, type] = {}
    for block in schema.blocks:
        fields = [(f.name, _pytype(f.raw_type)) for f in block.fields]
        classes[block.name] = make_typed_tuple(block.name, fields, {"make_int": make_int, "make_float": make_float, "make_str": make_str})
    return classes


def build_row(
    block: TemplateBlock,
    tuple_cls: type,
    values: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    """Convert {field: raw} into a typed NamedTuple row plus the string version."""
    raw: dict[str, Any] = {}
    for field in block.fields:
        value = values.get(field.name, field.default)
        raw[field.name] = make_str(value)
    row = tuple_cls(**raw)
    return row, raw