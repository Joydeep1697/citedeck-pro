"""Deterministic numeric and source-provenance verification."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

from atomic_claim_evidence import NUMBER_PATTERN


_UNIT_MULTIPLIERS = {
    "b": Decimal("1000000000"),
    "bn": Decimal("1000000000"),
    "billion": Decimal("1000000000"),
    "m": Decimal("1000000"),
    "million": Decimal("1000000"),
    "k": Decimal("1000"),
    "thousand": Decimal("1000"),
    "cr": Decimal("10000000"),
    "crore": Decimal("10000000"),
    "lakh": Decimal("100000"),
}


class AtomicContentVerifierV6:
    def normalize_number(self, value_str: str) -> dict:
        raw = str(value_str or "").strip()
        number = re.search(r"-?\d[\d,]*(?:\.\d+)?", raw)
        if number is None:
            return {"raw": raw, "numeric": None, "unit": None, "normalized": None, "percent": False}

        try:
            numeric = Decimal(number.group(0).replace(",", ""))
        except InvalidOperation:
            return {"raw": raw, "numeric": None, "unit": None, "normalized": None, "percent": False}

        suffix = raw[number.end() :].strip().lower().rstrip("%").strip()
        unit = suffix or None
        normalized = numeric * _UNIT_MULTIPLIERS.get(suffix, Decimal("1"))
        return {
            "raw": raw,
            "numeric": float(numeric),
            "unit": unit,
            "normalized": float(normalized),
            "normalized_decimal": normalized,
            "percent": raw.endswith("%"),
        }

    def _same_number(self, left: str, right: str) -> bool:
        first = self.normalize_number(left)
        second = self.normalize_number(right)
        if first.get("normalized_decimal") is None or second.get("normalized_decimal") is None:
            return False
        if first["percent"] != second["percent"]:
            return False
        tolerance = max(abs(first["normalized_decimal"]) * Decimal("0.000001"), Decimal("0.000000001"))
        return abs(first["normalized_decimal"] - second["normalized_decimal"]) <= tolerance

    def does_passage_contain_number(self, claimed_value: str, passage: str) -> dict:
        passage_numbers = [match.group(0).strip() for match in NUMBER_PATTERN.finditer(str(passage or ""))]
        matching = [value for value in passage_numbers if self._same_number(claimed_value, value)]
        exact_match = any(value.casefold() == claimed_value.strip().casefold() for value in matching)
        conflicts = [value for value in passage_numbers if not self._same_number(claimed_value, value)]
        supports = bool(matching)
        return {
            "supports": supports,
            "exact_match": exact_match,
            "normalized_match": supports,
            "conflicting_numbers": conflicts,
            "reason": (
                f"Claimed {claimed_value} matches source value {matching[0]}"
                if supports
                else f"Claimed {claimed_value} is not present in the source passage"
            ),
            "adversarial_test_detected": bool(conflicts and not supports),
        }

    def verify_atomic_claim(self, numeric_span, evidence) -> dict:
        source = str(getattr(evidence, "source_file", "") or "")
        location = getattr(evidence, "exact_location", {}) or {}
        passage = str(getattr(evidence, "exact_passage", "") or "")
        content = self.does_passage_contain_number(numeric_span.value, passage)
        has_location = bool(
            not location.get("pending")
            and any(location.get(key) for key in ("page", "page_number", "cell", "cell_range", "paragraph", "url"))
        )
        source_is_real = bool(source and source != "pending_lookup")
        verified = bool(source_is_real and has_location and passage and content["supports"])
        return {
            "numeric_id": numeric_span.numeric_id,
            "claimed_value": numeric_span.value,
            "evidence_id": getattr(evidence, "evidence_id", None),
            "source": source,
            "location": location,
            "has_location": has_location,
            "has_passage": bool(passage),
            "content_supports": content["supports"],
            "exact_match": content["exact_match"],
            "conflicting_numbers": content["conflicting_numbers"],
            "reason": content["reason"] if source_is_real else "Evidence source is missing or synthetic",
            "verified": verified,
            "adversarial_test_passed": not content["adversarial_test_detected"],
        }
