from __future__ import annotations

from app.models.input_errors import InputError, InputErrorKind, RuleViolation
from app.models.resolvers import ResolutionResult
from app.schema.fast_rules import FastRulesTemplate


class StrictDTOValidator:
    """Fast rule: strictly required fields must resolve or the invoice is rejected."""

    def validate(self, schema: FastRulesTemplate, result: ResolutionResult) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for resolved_name in schema.strict_required:
            cleaned = result.cleaned.get(resolved_name)
            if cleaned is None or not cleaned.is_resolved or not cleaned.value:
                severity = "CRITICAL" if resolved_name in schema.condition_field_required else "CRITICAL"
                violations.append(RuleViolation(
                    field_name=resolved_name,
                    severity=severity,
                    message=(
                        f"strictly required field '{resolved_name}' is missing after "
                        "condition validation"
                    ),
                ))
        return violations


def violations_to_errors(violations: list[RuleViolation]) -> list[InputError]:
    return [
        InputError(
            kind=InputErrorKind.CONFLICT if v.severity == "CRITICAL" else InputErrorKind.EXTRACTION_FAILED,
            message=v.message,
        )
        for v in violations
    ]