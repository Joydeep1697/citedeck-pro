"""Claim/evidence domain objects used by the production verification pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Optional


# Longest units go first: otherwise ``25 billion`` gets parsed as ``25 b``.
NUMBER_PATTERN = re.compile(
    r"(?<![\w.])(?:[$₹£€¥]|(?:USD|INR|EUR|GBP)\s*)?"
    r"-?\d[\d,]*(?:\.\d+)?"
    r"(?:\s*(?:billion|million|thousand|crore|lakh|cr|bn|[bmk]))?"
    r"(?:\s*%)?(?!\w)",
    re.IGNORECASE,
)


@dataclass
class NumericSpan:
    numeric_id: str
    value: str
    char_start: int
    char_end: int
    evidence_id: Optional[str] = None
    verification_status: str = "UNMAPPED"


@dataclass
class AtomicClaim:
    claim_id: str
    statement: str
    slide_number: int
    numeric_spans: list[NumericSpan]
    evidence_ids: list[str]
    visible_citation: str
    hidden_metadata: dict = field(default_factory=dict)


@dataclass
class AtomicEvidence:
    evidence_id: str
    source_file: str
    exact_location: dict
    exact_passage: str
    char_span_in_source: Optional[tuple[int, int]] = None
    url: Optional[str] = None


class AtomicClaimBuilder:
    """Create claims without inventing evidence for unsupported numbers."""

    def __init__(self) -> None:
        self.numeric_counter = 0
        self.claim_counter = 40
        self.evidence_counter = 100
        self.evidences: list[AtomicEvidence] = []
        self.claims: list[AtomicClaim] = []

    def add_atomic_evidence(
        self,
        source_file: str,
        exact_location: dict,
        exact_passage: str,
        char_span: Optional[tuple[int, int]] = None,
        url: Optional[str] = None,
        **_: object,
    ) -> str:
        source_file = str(source_file or "").strip()
        exact_passage = str(exact_passage or "").strip()
        if not source_file or source_file == "pending_lookup":
            raise ValueError("Evidence must come from a real, named source")
        if not exact_passage:
            raise ValueError("Evidence must contain an actual source passage")
        if not exact_location or exact_location.get("pending"):
            raise ValueError("Evidence must contain a real page, cell, paragraph, or URL")

        self.evidence_counter += 1
        evidence = AtomicEvidence(
            evidence_id=f"EVIDENCE-{self.evidence_counter}",
            source_file=source_file,
            exact_location={key: value for key, value in exact_location.items() if value is not None},
            exact_passage=exact_passage[:1000],
            char_span_in_source=char_span,
            url=url,
        )
        self.evidences.append(evidence)
        return evidence.evidence_id

    def add_atomic_claim(self, statement: str, slide_number: int, visible_citation: str) -> AtomicClaim:
        statement = str(statement or "").strip()
        if not statement:
            raise ValueError("Claims cannot be empty")

        self.claim_counter += 1
        spans: list[NumericSpan] = []
        for match in NUMBER_PATTERN.finditer(statement):
            self.numeric_counter += 1
            spans.append(
                NumericSpan(
                    numeric_id=f"NUM-{self.numeric_counter:03d}",
                    value=match.group(0).strip(),
                    char_start=match.start(),
                    char_end=match.end(),
                )
            )

        claim = AtomicClaim(
            claim_id=f"CLAIM-{self.claim_counter:03d}",
            statement=statement,
            slide_number=slide_number,
            numeric_spans=spans,
            evidence_ids=[],
            visible_citation=visible_citation,
        )
        self.claims.append(claim)
        return claim

    def link_number_to_evidence(self, claim_id: str, numeric_value: str, evidence_id: str) -> bool:
        claim = next((item for item in self.claims if item.claim_id == claim_id), None)
        evidence = next((item for item in self.evidences if item.evidence_id == evidence_id), None)
        if claim is None or evidence is None:
            return False

        for span in claim.numeric_spans:
            if span.value == numeric_value:
                span.evidence_id = evidence_id
                span.verification_status = "MAPPED"
                claim.evidence_ids = list(dict.fromkeys(item.evidence_id for item in claim.numeric_spans if item.evidence_id))
                return True
        return False
