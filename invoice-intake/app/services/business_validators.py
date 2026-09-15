from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from app.models.input_errors import RuleViolation


@dataclass
class BusinessValidationResult:
    violations: list[RuleViolation] = dc_field(default_factory=list)

    @property
    def critical(self) -> list[RuleViolation]:
        return [v for v in self.violations if v.severity == "CRITICAL"]

    @property
    def warnings(self) -> list[RuleViolation]:
        return [v for v in self.violations if v.severity == "WARNING"]

    @property
    def reason_codes(self) -> list[str]:
        codes = set()
        for v in self.violations:
            if "AMOUNT_MISMATCH" in v.message:
                codes.add("AMOUNT_MISMATCH")
            if "date" in v.message.lower() or "INVALID_DATE" in v.message:
                codes.add("INVALID_DATE")
            if "subtotal" in v.message.lower():
                codes.add("AMOUNT_MISMATCH")
        return sorted(codes)


def validate_business(
    *,
    issue_date: str | None,
    due_date: str | None,
    subtotal: int | None,
    tax_amount: int | None,
    total_amount: int | None,
    line_amount: int | None,
) -> BusinessValidationResult:
    result = BusinessValidationResult()

    if not issue_date:
        result.violations.append(RuleViolation(
            field_name="issue_date",
            severity="CRITICAL",
            message="INVALID_DATE issue_date is missing",
        ))
    if subtotal is not None and tax_amount is not None and total_amount is not None:
        if subtotal + tax_amount != total_amount:
            result.violations.append(RuleViolation(
                field_name="total_amount",
                severity="WARNING",
                message=f"AMOUNT_MISMATCH subtotal({subtotal}) + tax({tax_amount}) != total({total_amount})",
            ))
    if line_amount is not None and total_amount is not None:
        tolerance = max(1, int(total_amount * 0.02))
        if abs(line_amount - total_amount) > tolerance:
            result.violations.append(RuleViolation(
                field_name="total_amount",
                severity="WARNING",
                message=f"AMOUNT_MISMATCH line items sum {line_amount} vs total {total_amount}",
            ))
    if issue_date and due_date and due_date < issue_date:
        result.violations.append(RuleViolation(
            field_name="due_date",
            severity="CRITICAL",
            message="INVALID_DATE due_date is before issue_date",
        ))
    return result