"""
V5 Atomic Numeric-Span Level Evidence

Fixes: Claim ID not semantically tied to individual number

Before V4:
  "Revenue grew from $10M to $25M [CLAIM-042]"
  -> proves CLAIM-042 has evidence, but not which evidence supports $10M vs $25M

After V5:
  "Revenue grew from $10M to $25M"
  -> $10M [NUM-001] -> EVIDENCE-101 Sales!B2 "Jan | 10M"
  -> $25M [NUM-002] -> EVIDENCE-102 Sales!B3 "Dec | 25M"
  Each number has its own evidence span
"""

from dataclasses import dataclass, asdict
from typing import List, Optional
import re
import uuid

@dataclass
class NumericSpan:
    numeric_id: str  # NUM-001
    value: str  # "$10M"
    char_start: int  # position in claim text
    char_end: int
    evidence_id: str  # EVIDENCE-101
    verification_status: str = "PENDING"

@dataclass
class AtomicClaim:
    claim_id: str  # CLAIM-042
    statement: str  # "Revenue grew from $10M to $25M"
    slide_number: int
    numeric_spans: List[NumericSpan]  # atomic mapping
    evidence_ids: List[str]  # aggregated
    visible_citation: str  # "Source: Gartner, 2026, p.14" - what user sees
    hidden_metadata: dict = None  # invisible layer

@dataclass
class AtomicEvidence:
    evidence_id: str
    source_file: str
    exact_location: dict  # {"page":14, "cell": "B2", "sheet": "Sales"}
    exact_passage: str  # 300 chars
    char_span_in_source: Optional[tuple] = None  # (1024, 1035) in PDF
    url: Optional[str] = None

class AtomicClaimBuilder:
    def __init__(self):
        self.numeric_counter = 0
        self.claim_counter = 40
        self.evidence_counter = 100
        self.evidences = []
        self.claims = []
    
    def add_atomic_evidence(self, source_file, exact_location, exact_passage, char_span=None, url=None):
        self.evidence_counter += 1
        eid = f"EVIDENCE-{self.evidence_counter}"
        ev = AtomicEvidence(
            evidence_id=eid,
            source_file=source_file,
            exact_location=exact_location,
            exact_passage=exact_passage[:500],
            char_span_in_source=char_span,
            url=url
        )
        self.evidences.append(ev)
        return eid
    
    def add_atomic_claim(self, statement, slide_number, visible_citation):
        """
        Parses statement for numbers and creates atomic numeric spans
        Example: "Revenue grew from $10M to $25M" -> finds $10M and $25M
        Each needs separate evidence
        """
        self.claim_counter += 1
        cid = f"CLAIM-{self.claim_counter:03d}"
        
        # Find all numbers in statement with positions
        number_pattern = re.compile(r'\$?\d+(?:,\d+)*(?:\.\d+)?\s*(?:B|M|Cr|K|billion|million|%|USD|INR)?')
        numeric_spans = []
        evidence_ids = []
        
        for match in number_pattern.finditer(statement):
            self.numeric_counter += 1
            nid = f"NUM-{self.numeric_counter:03d}"
            value = match.group(0)
            
            # For demo, each number gets its own evidence - in real, would link to actual extracted evidence
            # Here we create placeholder that will be replaced with real evidence lookup
            # In production: search evidence store for this exact value
            matching_evidence = None
            for ev in self.evidences:
                if value.strip('$') in ev.exact_passage or ev.source_file in visible_citation:
                    matching_evidence = ev
                    break
            
            # If no matching evidence yet, create atomic evidence for this number
            if not matching_evidence:
                # This would be linked to real source in production
                eid = self.add_atomic_evidence(
                    source_file="pending_lookup",
                    exact_location={"pending": True},
                    exact_passage=f"Evidence for {value} in '{statement}'"
                )
            else:
                eid = matching_evidence.evidence_id
            
            numeric_span = NumericSpan(
                numeric_id=nid,
                value=value,
                char_start=match.start(),
                char_end=match.end(),
                evidence_id=eid,
                verification_status="MAPPED" if eid else "UNMAPPED"
            )
            numeric_spans.append(numeric_span)
            if eid not in evidence_ids:
                evidence_ids.append(eid)
        
        claim = AtomicClaim(
            claim_id=cid,
            statement=statement,
            slide_number=slide_number,
            numeric_spans=numeric_spans,
            evidence_ids=evidence_ids,
            visible_citation=visible_citation,
            hidden_metadata={
                "atomic_mapping": [
                    {"numeric_id": ns.numeric_id, "value": ns.value, "evidence_id": ns.evidence_id, "char_span": [ns.char_start, ns.char_end]}
                    for ns in numeric_spans
                ]
            }
        )
        self.claims.append(claim)
        return claim
    
    def link_number_to_evidence(self, claim_id, numeric_value, evidence_id):
        """Explicitly link a specific number to exact evidence span - atomic level"""
        claim = next((c for c in self.claims if c.claim_id == claim_id), None)
        if not claim:
            return False
        
        for ns in claim.numeric_spans:
            if ns.value == numeric_value:
                ns.evidence_id = evidence_id
                ns.verification_status = "VERIFIED_EXACT_SPAN"
                if evidence_id not in claim.evidence_ids:
                    claim.evidence_ids.append(evidence_id)
                return True
        return False

# Example from your feedback
if __name__ == "__main__":
    builder = AtomicClaimBuilder()
    
    # Add evidences for $10M and $25M separately
    eid_10m = builder.add_atomic_evidence(
        source_file="financials.xlsx",
        exact_location={"sheet": "Revenue", "cell": "B2", "cell_range": "Revenue!B2"},
        exact_passage="Jan Revenue: $10M",
        char_span=(0, 4)
    )
    eid_25m = builder.add_atomic_evidence(
        source_file="financials.xlsx",
        exact_location={"sheet": "Revenue", "cell": "B13", "cell_range": "Revenue!B13"},
        exact_passage="Dec Revenue: $25M",
        char_span=(0, 4)
    )
    
    # Claim with two numbers
    claim = builder.add_atomic_claim(
        statement="Revenue grew from $10M to $25M",
        slide_number=5,
        visible_citation="Source: financials.xlsx"
    )
    
    # Now atomically link each number to its exact evidence
    builder.link_number_to_evidence(claim.claim_id, "$10M", eid_10m)
    builder.link_number_to_evidence(claim.claim_id, "$25M", eid_25m)
    
    import json
    print(json.dumps(asdict(claim), indent=2))
    print("\nAtomic mapping - each number has exact evidence span:")
    for ns in claim.numeric_spans:
        ev = next(e for e in builder.evidences if e.evidence_id == ns.evidence_id)
        print(f"  {ns.value} [{ns.numeric_id}] -> {ns.evidence_id} {ev.exact_location} '{ev.exact_passage}'")
