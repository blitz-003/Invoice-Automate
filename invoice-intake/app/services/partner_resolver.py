from __future__ import annotations

from app.models.invoice import PartnerMatch
from app.services.similarity import max_ngram_relation
from app.utils.normalization import normalized_key, strip_company_suffix


class PartnerMatcher:
    """Resolves an extracted supplier name to a known partner (companies table)."""

    def __init__(self, partners: list):
        self._partners = [p for p in partners if getattr(p, "name", None)]
        self._by_key = {
            normalized_key(p.name): p
            for p in self._partners
            if normalized_key(p.name)
        }
        self._aliases: dict[str, object] = {}
        for p in self._partners:
            for alias in getattr(p, "aliases", []) or []:
                key = normalized_key(alias)
                if key and key not in self._aliases:
                    self._aliases[key] = p

    def match(self, supplier_name: str | None) -> PartnerMatch:
        if not supplier_name:
            return PartnerMatch.no_match("Supplier name is missing")
        key = normalized_key(supplier_name)
        if not key:
            return PartnerMatch.no_match("Supplier name is missing")

        direct = self._by_key.get(key)
        if direct is not None:
            return PartnerMatch(matched=True, partner_code=direct.partner_code,
                                confidence=0.99, reason="exact normalized-name match",
                                matched_name=direct.name)

        alias = self._aliases.get(key)
        if alias is not None:
            return PartnerMatch(matched=True, partner_code=alias.partner_code,
                                confidence=0.95, reason="alias match",
                                matched_name=alias.name)

        best = None
        best_score = 0.0
        for p in self._partners:
            score = max_ngram_relation(3, key, normalized_key(p.name))
            if score > best_score:
                best_score = score
                best = p
        if best is not None and best_score >= 0.8:
            return PartnerMatch(matched=True, partner_code=best.partner_code,
                                confidence=round(best_score, 3), reason="fuzzy name match",
                                matched_name=best.name)
        return PartnerMatch.no_match(
            f"No reliable partner match for '{supplier_name}' (best {1.0 if best is None else 0.0:.2f})"
        )


def normalize_supplier_name(value: str) -> str:
    return strip_company_suffix(value)