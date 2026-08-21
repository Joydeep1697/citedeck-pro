"""
Implements the strict architecture you suggested:

Slide claim
    ↓
Claim ID
    ↓
Evidence ID
    ↓
Exact source location
    ↓
Verification result

Example:
CLAIM-042 "Market will reach $25B by 2030"
SUPPORTED BY: EVIDENCE-117 Source: market_report.pdf Page: 14 Exact passage: ...
"""

import uuid
from dataclasses import dataclass, asdict
from typing import List, Optional

@dataclass
class Evidence:
    evidence_id: str
    source_file: str
    source_type: str  # pdf, excel, web, docx
    exact_location: dict  # {"page": 14, "cell": "B12", "url": "...", "paragraph": 5}
    exact_passage: str  # 300 char snippet
    char_span: Optional[tuple] = None  # (start, end) in source doc
    url: Optional[str] = None
    verification_status: str = "EXTRACTED"

@dataclass
class Claim:
    claim_id: str
    statement: str  # "Market will reach $25B by 2030"
    slide_number: int
    evidence_ids: List[str]  # ["EVIDENCE-117"]
    verification_status: str = "PENDING"
    numerical_values: List[str] = None

@dataclass
class ClaimEvidenceGraph:
    claims: List[Claim]
    evidences: List[Evidence]
    
    def to_audit_json(self):
        return {
            "claims": [asdict(c) for c in self.claims],
            "evidences": [asdict(e) for e in self.evidences],
            "graph": [
                {
                    "claim_id": c.claim_id,
                    "statement": c.statement,
                    "slide": c.slide_number,
                    "supported_by": [
                        {
                            "evidence_id": eid,
                            "source": next((ev.source_file for ev in self.evidences if ev.evidence_id == eid), "UNKNOWN"),
                            "location": next((ev.exact_location for ev in self.evidences if ev.evidence_id == eid), {}),
                            "passage": next((ev.exact_passage for ev in self.evidences if ev.evidence_id == eid), "")[:200]
                        }
                        for eid in c.evidence_ids
                    ]
                }
                for c in self.claims
            ]
        }

class ClaimEvidenceBuilder:
    def __init__(self):
        self.evidence_counter = 100
        self.claim_counter = 10
        self.evidences = []
        self.claims = []
    
    def add_evidence(self, source_file, source_type, exact_location, exact_passage, url=None, char_span=None):
        self.evidence_counter += 1
        eid = f"EVIDENCE-{self.evidence_counter}"
        ev = Evidence(
            evidence_id=eid,
            source_file=source_file,
            source_type=source_type,
            exact_location=exact_location,
            exact_passage=exact_passage[:500],
            char_span=char_span,
            url=url,
            verification_status="VERIFIED"
        )
        self.evidences.append(ev)
        return eid
    
    def add_claim(self, statement, slide_number, evidence_ids, numerical_values=None):
        self.claim_counter += 1
        cid = f"CLAIM-{self.claim_counter:03d}"
        claim = Claim(
            claim_id=cid,
            statement=statement,
            slide_number=slide_number,
            evidence_ids=evidence_ids,
            verification_status="VERIFIED" if evidence_ids else "UNVERIFIED",
            numerical_values=numerical_values or []
        )
        self.claims.append(claim)
        return cid
    
    def build_from_facts(self, facts, slide_number=1):
        """Builds graph from extracted facts - each fact becomes evidence, claim links to it"""
        for fact in facts:
            # Evidence with exact location
            exact_location = {}
            if fact.get("page_number"):
                exact_location = {"page": fact["page_number"], "char_start": fact.get("char_start"), "char_end": fact.get("char_end")}
            elif fact.get("cell_range"):
                exact_location = {"cell_range": fact["cell_range"], "sheet": fact.get("sheet"), "cell": fact.get("cell")}
            elif fact.get("url"):
                exact_location = {"url": fact["url"], "tavily_score": fact.get("score")}
            
            eid = self.add_evidence(
                source_file=fact["source_file"],
                source_type=fact.get("source_type", "unknown"),
                exact_location=exact_location,
                exact_passage=fact.get("source_text", fact.get("claim",""))[:500],
                url=fact.get("url"),
                char_span=(fact.get("char_start"), fact.get("char_end")) if fact.get("char_start") else None
            )
            
            # Claim that is supported by this evidence
            statement = fact.get("claim", "")[:200]
            numerical = [fact.get("claim")] if any(c.isdigit() for c in fact.get("claim","")) else []
            
            self.add_claim(
                statement=statement,
                slide_number=slide_number,
                evidence_ids=[eid],
                numerical_values=numerical
            )
        
        return ClaimEvidenceGraph(claims=self.claims, evidences=self.evidences)

# Example from your feedback
if __name__ == "__main__":
    builder = ClaimEvidenceBuilder()
    
    # Your example: CLAIM-042 supported by EVIDENCE-117
    eid = builder.add_evidence(
        source_file="market_report.pdf",
        source_type="pdf",
        exact_location={"page": 14, "char_start": 1024, "char_end": 1050},
        exact_passage="The EV charging market will reach $25B by 2030 according to...",
        url=None
    )
    print(f"Created {eid}")
    
    cid = builder.add_claim(
        statement="Market will reach $25B by 2030",
        slide_number=7,
        evidence_ids=[eid],
        numerical_values=["$25B"]
    )
    print(f"Created {cid} -> supported by {eid}")
    
    graph = ClaimEvidenceGraph(claims=builder.claims, evidences=builder.evidences)
    import json
    print(json.dumps(graph.to_audit_json(), indent=2)[:1000])
