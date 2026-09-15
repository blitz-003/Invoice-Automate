from __future__ import annotations

import re
from datetime import date

from app.models.resolvers import CleanedValue, ResolutionContext, ResolutionResult
from app.schema.fast_rules import FastRulesTemplate

_DATE_RE = re.compile(r"^(19|20)\d{2}[年/.\-]\s*\d{1,2}[月/.\-]\s*\d{1,2}日?$")
_NUM_CURRENCY_RE = re.compile(r"([¥￥]\s*)?([\d,]+(?:\.\d+)?)\s*(円)?")
_NUM_RE = re.compile(r"[\d,]+(?:\.\d+)?")

FIELDS_TO_SKIP = {"Ord"}
NUMBER_Y = ["Amount", "Total", "Tax", "Price", "Quantity", "UnitPrice", "LineAmount", "TaxTotal"]
DATE_Y = ["Date", "PrintDate", "IssueDate", "DueDate"]


class FieldResolver:
    """Resolves raw extracted strings into cleaned values per field type."""

    def resolve(
        self,
        schema: FastRulesTemplate,
        data_header: dict[str, str],
        context: ResolutionContext,
    ) -> ResolutionResult:
        values = dict(data_header)
        values.update({k: v for k, v in context.overrides.items() if v})
        result = ResolutionResult()
        for block in schema.blocks:
            if block.rows_constant != 1:
                continue
            for field in block.fields:
                resolved_name = f"{block.name}.{field.name}"
                if field.name in FIELDS_TO_SKIP:
                    continue
                raw = values.get(resolved_name, "")
                cleaned = self._clean(field.name, raw, context.is_prefill)
                if cleaned is None:
                    if field.required or resolved_name in schema.strict_required:
                        result.errors.append(_make_error(resolved_name, "UNRESOLVED",
                                                         f"{resolved_name} could not be resolved."))
                    continue
                result.cleaned[resolved_name] = cleaned
        return result

    def _clean(self, field_name: str, raw: str, is_prefill: bool) -> CleanedValue | None:
        if not raw:
            return None
        if any(tag in field_name for tag in NUMBER_Y):
            text = _NUM_CURRENCY_RE.sub(r"\2", raw).strip()
            m = _NUM_RE.search(text)
            if not m:
                return CleanedValue.unresolved(field_name, "NOT_A_NUMBER",
                                               f"{field_name} value is not numeric: {raw}")
            num_text = m.group(0).replace(",", "")
            return CleanedValue.resolved(
                field_name, num_text,
                is_number=True,
                numeric_value=float(num_text),
                confidence=0.9 if is_prefill else 0.5,
                note="prefilled by provider" if is_prefill else "",
            )
        if any(tag in field_name for tag in DATE_Y):
            text = raw.strip()
            m = _DATE_RE.match(text)
            if not m:
                return CleanedValue.unresolved(field_name, "NOT_A_DATE",
                                               f"{field_name} value is not a parseable date: {raw}")
            nums = re.findall(r"\d{1,4}", text)
            year, month, day = (int(nums[0]), int(nums[1]), int(nums[2]))
            try:
                d = date(year, month, day)
            except ValueError:
                return CleanedValue.unresolved(field_name, "INVALID_DATE",
                                               f"{field_name} has an impossible date: {raw}")
            return CleanedValue.resolved(field_name, d.isoformat(),
                                         confidence=0.9 if is_prefill else 0.5,
                                         note="prefilled by provider" if is_prefill else "")
        cleaned = _strip_punct(raw)
        return CleanedValue.resolved(field_name, cleaned,
                                     confidence=0.9 if is_prefill else 0.5,
                                     note="prefilled by provider" if is_prefill else "")


def _strip_punct(value: str) -> str:
    import unicodedata

    value = value.replace("\n", " ").replace("\t", " ")
    value = " ".join(value.split())
    for ch in ",，.。、;；":
        value = value.rstrip(ch)
    return value.strip()


def _make_error(field: str, code: str, message: str):
    from app.models.input_errors import InputError, InputErrorKind
    from app.models.resolvers import ErrorSetting

    return ErrorSetting(err_code=code, message=message, field_name=field)