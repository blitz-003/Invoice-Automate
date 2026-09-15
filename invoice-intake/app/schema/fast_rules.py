from __future__ import annotations

import math
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Optional

import yaml

# ---------------------------------------------------------------------------
# Default schema used when config/fast_rules_schema.yaml is absent. A demo
# invoice template is honest-data invoicing; fields mirror the submission docs.
# ---------------------------------------------------------------------------

DEFAULT_SCHEMA: dict[str, Any] = {
    "rules": "fast_rules",
    "tuple_name": "InvoiceData",
    "key_field": "InvoiceNumber",
    "blocks": [
        {
            "name": "SellerInfo",
            "label": "売り手情報",
            "rows_constant": 1,
            "fields": [
                {"name": "SellerName", "type": "str", "required": True, "label": "売り手名"},
                {"name": "SellerAddress", "type": "str", "label": "売り手住所"},
                {"name": "SellerTaxId", "type": "str", "label": "売り手登録番号"},
            ],
        },
        {
            "name": "BuyerInfo",
            "label": "買い手情報",
            "rows_constant": 1,
            "fields": [
                {"name": "BuyerName", "type": "str", "required": True, "label": "買い手名"},
                {"name": "BuyerAddress", "type": "str", "label": "買い手住所"},
                {"name": "BuyerTaxCode", "type": "str", "label": "買い手登録番号"},
            ],
        },
        {
            "name": "Invoice",
            "label": "請求書",
            "rows_constant": 1,
            "fields": [
                {"name": "InvoiceNumber", "type": "str", "required": True, "label": "請求書番号"},
                {"name": "IssueDate", "type": "str", "label": "発行日"},
                {"name": "DueDate", "type": "str", "label": "支払期日"},
                {"name": "Currency", "type": "str", "default": "JPY", "label": "通貨"},
                {"name": "TotalAmount", "type": "str", "label": "請求金額"},
                {"name": "Subtotal", "type": "str", "label": "小計"},
                {"name": "TaxTotal", "type": "str", "label": "消費税"},
            ],
        },
        {
            "name": "Item",
            "label": "明細",
            "rows_constant": "n",
            "ordinal_field": "Ord",
            "postprocess_hint": "aggregation",
            "fields": [
                {"name": "Ord", "type": "int", "required": True, "label": "行"},
                {"name": "ItemName", "type": "str", "label": "品名"},
                {"name": "Quantity", "type": "float", "label": "数量"},
                {"name": "Unit", "type": "str", "label": "単位"},
                {"name": "UnitPrice", "type": "float", "label": "単価"},
                {"name": "LineAmount", "type": "float", "label": "金額"},
                {"name": "TaxRate", "type": "int", "label": "税率(10/8)"},
                {"name": "Notes", "type": "str", "label": "備考"},
            ],
        },
    ],
    "pre_conditions": ["field_for('Invoice.InvoiceNumber') is not None"],
    "post_conditions": ["aggregate_total_cross_check() is truthful"],
    "strict_required": [
        "SellerInfo.SellerName",
        "BuyerInfo.BuyerName",
        "Invoice.InvoiceNumber",
        "Invoice.TotalAmount",
    ],
    "condition_field_required": ["Invoice.InvoiceNumber"],
}


def _deep_default() -> dict[str, Any]:
    import copy

    return copy.deepcopy(DEFAULT_SCHEMA)


@dataclass
class TemplateField:
    name: str
    raw_type: str
    required: bool = False
    default: str = ""
    label: str = ""

    @property
    def is_item_scalar(self) -> bool:
        return self.raw_type in ("int", "float", "number")


@dataclass
class TemplateBlock:
    name: str
    label: str
    rows_constant: Optional[int]
    fields: list[TemplateField]
    ordinal_field: Optional[str] = None
    postprocess_hint: Optional[str] = None
    ref_name: Optional[str] = None

    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]


@dataclass
class FastRulesTemplate:
    rules: str
    tuple_name: str
    key_field: str
    blocks: list[TemplateBlock]
    strict_required: list[str]
    condition_field_required: list[str]

    @property
    def header_blocks(self) -> list[TemplateBlock]:
        return [b for b in self.blocks if b.name in ("SellerInfo", "BuyerInfo", "Invoice")]

    @property
    def item_block(self):
        return next((b for b in self.blocks if b.rows_constant != 1), None)

    def all_fields(self) -> list[TemplateField]:
        return [f for b in self.blocks for f in b.fields]

    def resolved_names(self, block: TemplateBlock) -> list[str]:
        return [f"{block.name}.{f.name}" for f in block.fields]


def load_schema(path: Optional[str] = None) -> FastRulesTemplate:
    if path:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        return _from_dict(raw)
    if Path("config/fast_rules_schema.yaml").exists():
        with open("config/fast_rules_schema.yaml", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        return _from_dict(raw)
    return _from_dict(_deep_default())


def _from_dict(raw: dict[str, Any]) -> FastRulesTemplate:
    blocks: list[TemplateBlock] = []
    for b in raw.get("blocks", []):
        fields = [
            TemplateField(
                name=f.get("name", ""),
                raw_type=f.get("type", "str"),
                required=bool(f.get("required", False)),
                default=f.get("default", ""),
                label=f.get("label", ""),
            )
            for f in b.get("fields", [])
        ]
        rows = b.get("rows_constant")
        rows_constant = None if rows == "n" else int(rows) if rows is not None else 1
        blocks.append(
            TemplateBlock(
                name=b.get("name", ""),
                label=b.get("label", ""),
                rows_constant=rows_constant,
                fields=fields,
                ordinal_field=b.get("ordinal_field"),
                postprocess_hint=b.get("postprocess_hint"),
                ref_name=b.get("ref_name"),
            )
        )
    return FastRulesTemplate(
        rules=raw.get("rules", "fast_rules"),
        tuple_name=raw.get("tuple_name", "InvoiceData"),
        key_field=raw.get("key_field", "InvoiceNumber"),
        blocks=blocks,
        strict_required=raw.get("strict_required", []),
        condition_field_required=raw.get("condition_field_required", []),
    )


_YEAR_RE = re.compile(r"(19|20)\d{2}(?:年)?", re.UNICODE)


def field_for(block_and_field: str, values: dict[str, str]) -> Optional[str]:
    """Fast-rule helper: values keyed by 'Block.Field'."""
    return values.get(block_and_field)


def normalize_amount(value: str) -> Optional[float]:
    if not value:
        return None
    cleaned = value.replace(",", "").replace("￥", "").replace("¥", "")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_year(value: str) -> Optional[str]:
    m = _YEAR_RE.search(value)
    if not m:
        return None
    return m.group(0)[:4]


_AMOUNT_WORDS = ["合計", "御請求金額", "請求金額", "総計", "小計"]


def aggregate_total_cross_check(amount: Optional[float], line_total: Optional[float]) -> bool:
    if amount is None or line_total is None:
        return True
    return abs(amount - line_total) <= max(1.0, amount * 0.02)