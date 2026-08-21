"""Evidence retrieval that never maps claims to synthetic or unrelated rows."""

from __future__ import annotations

import re

from atomic_content_verifier_v6 import AtomicContentVerifierV6


_STOP_WORDS = {"about", "after", "also", "and", "been", "from", "have", "into", "that", "the", "their", "this", "will", "with"}
_METRIC_FAMILIES = ({"revenue", "sales", "income"}, {"expense", "expenses", "cost", "costs"}, {"profit", "margin"}, {"customers", "users", "subscribers"})


class EvidenceRetrieverV6:
    def __init__(self) -> None:
        self.verifier = AtomicContentVerifierV6()

    def extract_keywords(self, text: str, min_len: int = 3) -> set[str]:
        return {
            word
            for word in re.findall(r"[a-zA-Z]+", str(text or "").casefold())
            if len(word) >= min_len and word not in _STOP_WORDS
        }

    def score_evidence_for_number(self, claimed_value: str, claim_statement: str, evidence) -> dict:
        passage = str(getattr(evidence, "exact_passage", "") or "")
        source = str(getattr(evidence, "source_file", "") or "")
        location = getattr(evidence, "exact_location", {}) or {}
        match = self.verifier.does_passage_contain_number(claimed_value, passage)
        provenance = bool(source and source != "pending_lookup" and location and not location.get("pending"))

        if not match["supports"] or not provenance:
            return {
                "evidence_id": getattr(evidence, "evidence_id", None),
                "source": source,
                "score": 0,
                "reasons": [match["reason"] if provenance else "Evidence has no trustworthy provenance"],
                "passage_preview": passage[:140],
                "suitable": False,
            }

        claim_words = self.extract_keywords(claim_statement)
        passage_words = self.extract_keywords(passage)
        overlap = claim_words & passage_words
        score = 65 + min(len(overlap) * 7, 28)
        reasons = [match["reason"]]
        if overlap:
            reasons.append("Context overlap: " + ", ".join(sorted(overlap)))

        for family in _METRIC_FAMILIES:
            if claim_words & family and not passage_words & family:
                if any(passage_words & other for other in _METRIC_FAMILIES if other is not family):
                    score -= 45
                    reasons.append("Source describes a different business metric")

        if source.casefold() in claim_statement.casefold():
            score += 8

        return {
            "evidence_id": evidence.evidence_id,
            "source": source,
            "score": score,
            "reasons": reasons,
            "passage_preview": passage[:140],
            "suitable": score >= 60,
        }

    def retrieve_best_evidence(self, claimed_value: str, claim_statement: str, evidence_store: list, top_k: int = 3) -> list[dict]:
        ranked = [self.score_evidence_for_number(claimed_value, claim_statement, evidence) for evidence in evidence_store]
        return sorted(ranked, key=lambda result: result["score"], reverse=True)[:top_k]

    def link_claim_atomically(self, claim, evidence_store: list) -> list[dict]:
        linked = []
        for span in claim.numeric_spans:
            ranked = self.retrieve_best_evidence(span.value, claim.statement, evidence_store, top_k=1)
            if ranked and ranked[0]["suitable"]:
                best = ranked[0]
                span.evidence_id = best["evidence_id"]
                span.verification_status = "MAPPED"
                linked.append({"numeric_id": span.numeric_id, "value": span.value, "linked_to": span.evidence_id, "score": best["score"], "reasons": best["reasons"], "suitable": True})
            else:
                span.evidence_id = None
                span.verification_status = "UNMAPPED"
                linked.append({"numeric_id": span.numeric_id, "value": span.value, "linked_to": None, "score": 0, "reasons": ["No source passage independently supports this number"], "suitable": False})

        claim.evidence_ids = list(dict.fromkeys(span.evidence_id for span in claim.numeric_spans if span.evidence_id))
        return linked
