from __future__ import annotations

from app.models.input_errors import InputError, RuleViolation
from app.models.resolvers import ResolutionResult
from app.schema.fast_rules import FastRulesTemplate
from app.services.validators import StrictDTOValidator, violations_to_errors


def validate(
    schema: FastRulesTemplate,
    resolution: ResolutionResult,
) -> tuple[list[RuleViolation], list[InputError]]:
    violations = StrictDTOValidator().validate(schema, resolution)
    errors = violations_to_errors(violations)
    return violations, errors