from __future__ import annotations

import collections
from typing import get_type_hints

_DYNAMIC_MODULE_MARKER = "__invoice_dynamic__"


def make_typed_tuple(
    name: str,
    fields: list[tuple[str, object]],
    localns: dict,
) -> type:
    """Build a NamedTuple with annotations kept for runtime value typing."""
    named = collections.namedtuple(name, [f for f, _ in fields])
    named.__annotations__ = {f: t for f, t in fields}
    named.__module__ = _DYNAMIC_MODULE_MARKER
    named._resolver_localns = dict(localns)
    return named


def resolve_annotations(cls):
    """Evaluate forward references against the localns captured at build time."""
    localns = getattr(cls, "_resolver_localns", None) or {}
    hints = get_type_hints(cls, localns=localns)
    return hints