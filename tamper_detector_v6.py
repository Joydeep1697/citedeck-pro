"""Compare every visible slide claim against every signed audit record."""

from __future__ import annotations

from collections import Counter
import re

from atomic_claim_evidence import NUMBER_PATTERN
from atomic_content_verifier_v6 import AtomicContentVerifierV6


class TamperDetectorV6:
    def __init__(self) -> None:
        self.verifier = AtomicContentVerifierV6()

    @staticmethod
    def extract_numbers(text: str) -> list[str]:
        return [match.group(0).strip() for match in NUMBER_PATTERN.finditer(str(text or ""))]

    @staticmethod
    def normalize_for_comparison(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").casefold().strip())

    def _normalized_numbers(self, numbers: list[str]) -> Counter:
        result = Counter()
        for value in numbers:
            normalized = self.verifier.normalize_number(value)
            key = (str(normalized.get("normalized_decimal")), normalized.get("percent", False))
            result[key] += 1
        return result

    def detect_tampering(self, slide, atomic_claim):
        claims = atomic_claim if isinstance(atomic_claim, list) else [atomic_claim]
        claims = [claim for claim in claims if claim is not None]
        title = slide.shapes.title
        body = []
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False) or shape == title:
                continue
            text = shape.text_frame.text or ""
            if text.strip().casefold().startswith("source:"):
                continue
            body.append(text)

        visible_text = "\n".join(body)
        visible_numbers = self.extract_numbers(visible_text)
        hidden_numbers = [span.value for claim in claims for span in claim.numeric_spans]
        visible_counts = self._normalized_numbers(visible_numbers)
        hidden_counts = self._normalized_numbers(hidden_numbers)
        issues = []
        if visible_counts != hidden_counts:
            issues.append(f"Visible slide numbers {visible_numbers} do not match audited claim numbers {hidden_numbers}")

        normalized_visible = self.normalize_for_comparison(visible_text)
        for claim in claims:
            if self.normalize_for_comparison(claim.statement) not in normalized_visible:
                issues.append(f"Audited claim {claim.claim_id} is missing or changed in the visible slide")

        return {
            "slide_number": getattr(slide, "slide_id", 0),
            "visible_text_preview": visible_text[:200],
            "hidden_statement": " | ".join(claim.statement for claim in claims),
            "visible_numbers": visible_numbers,
            "hidden_numbers": hidden_numbers,
            "hidden_statement_numbers": hidden_numbers,
            "tamper_detected": bool(issues),
            "issues": issues,
            "verified": not issues,
        }
