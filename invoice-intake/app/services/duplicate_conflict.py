from __future__ import annotations

import re
from typing import Optional

from app.models.duplicate_conflict import (
    ConflictFieldOutcome,
    ConflictAnomalySet,
    FoundDuplicate,
)
from app.models.resolvers import ResolutionResult
from app.schema.fast_rules import FastRulesTemplate
from app.services.similarity import max_ngram_relation


class StoredInvoice:
    """Lightweight shape of an invoice already persisted in the invoice store."""

    def __init__(self, data: dict):
        self.data = data

    @property
    def invoice_number(self) -> str:
        return self.data.get("Invoice.InvoiceNumber", "")

    @property
    def seller(self) -> str:
        return self.data.get("SellerInfo.SellerName", "")

    @property
    def total(self) -> str:
        value = self.data.get("Invoice.TotalAmount", "")
        return re.sub(r"[^0-9.]", "", value)


class DuplicateConflictService:
    def __init__(self, store):
        self.store = store
        self._conflict_seen: set[str] = set()
        self._duplicate_seen: set[str] = set()
        self._duplicate_candidates: list[FoundDuplicate] = []
        self._conflict_anomalies: list[ConflictAnomalySet] = []

    def check(
        self,
        schema: FastRulesTemplate,
        resolution: ResolutionResult,
    ) -> None:
        """Locates same-invoice duplicates from (affected) all-instances already stored."""
        key_field = (
            f"Invoice.{schema.key_field}"
            if "." not in schema.key_field
            else schema.key_field
        )
        key_value = resolution.cleaned.get(key_field)
        if key_value is None or not key_value.is_resolved or not key_value.value:
            return
        number = key_value.value
        existing = [StoredInvoice(d) for d in self.store.list_invoices()]
        duplicates = [
            inv for inv in existing
            if inv.invoice_number == number and inv.invoice_number
        ]
        for inv in duplicates:
            if inv.invoice_number in self._duplicate_seen:
                continue
            self._duplicate_seen.add(inv.invoice_number)
            self._duplicate_candidates.append(FoundDuplicate(
                invoice_id=inv.invoice_number,
                note="已验证存在の重複請求書候補。latest/1912規則で新規請求書を維持します。",
                reason="same invoice_number found in invoice store",
            ))

        self._resolve_conflicts(resolution, duplicates)

    def _resolve_conflicts(self, resolution: ResolutionResult, duplicates: list[StoredInvoice]) -> None:
        for resolved_name, cleaned in resolution.cleaned.items():
            others = [inv for inv in duplicates if self._stored_value(inv, resolved_name)]
            if not others:
                continue
            base = cleaned.value
            for inv in others:
                other_val = self._stored_value(inv, resolved_name)
                key = f"{resolved_name}|{base}|{other_val}"
                if key in self._conflict_seen:
                    continue
                self._conflict_seen.add(key)
                if base != other_val and base and other_val:
                    outcome = ConflictFieldOutcome(
                        field_name=resolved_name,
                        current_value=base,
                        other_value=other_val,
                        overwrite=False,
                    )
                    anomaly = ConflictAnomalySet(
                        field_name=resolved_name,
                        anomalies=[outcome.model_dump()],
                        is_resolved=False,
                        unresolved="conflicting values across all instances",
                    )
                    self._conflict_anomalies.append(anomaly)

    def _stored_value(self, invoice: StoredInvoice, resolved_name: str) -> str:
        return invoice.data.get(resolved_name, "")

    def duplicate_candidate(self) -> Optional[FoundDuplicate]:
        if not self._duplicate_candidates:
            return None
        return self._duplicate_candidates[0]

    def conflict_anomalies(self) -> list[ConflictAnomalySet]:
        return self._conflict_anomalies

    @staticmethod
    def seller_similarity(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return max_ngram_relation(3, a, b)