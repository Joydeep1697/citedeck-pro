"""Machine-readable slide audit metadata with optional keyed integrity checks."""

from __future__ import annotations

import hashlib
import hmac
import json
import os

from pptx.util import Inches, Pt


class InvisibleMetadataEngine:
    def __init__(self, signing_key: str | None = None) -> None:
        self.signing_key = signing_key if signing_key is not None else os.getenv("CITEDECK_SIGNING_KEY")

    @staticmethod
    def _canonical_bytes(payload: dict) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _integrity(self, payload: dict) -> dict:
        data = self._canonical_bytes(payload)
        if self.signing_key:
            return {"algorithm": "hmac-sha256", "value": hmac.new(self.signing_key.encode(), data, hashlib.sha256).hexdigest()}
        return {"algorithm": "sha256", "value": hashlib.sha256(data).hexdigest()}

    def validate_integrity(self, metadata: dict) -> bool:
        verification = metadata.get("citedeck_verification", {})
        stored = verification.get("integrity", {})
        if not stored:
            return False
        payload = {key: value for key, value in verification.items() if key != "integrity"}
        expected = self._integrity(payload)
        return stored.get("algorithm") == expected["algorithm"] and hmac.compare_digest(str(stored.get("value", "")), expected["value"])

    def add_invisible_metadata_to_slide(self, slide, atomic_claim, evidence_lookup: dict | None = None) -> None:
        claims = atomic_claim if isinstance(atomic_claim, list) else [atomic_claim]
        claims = [claim for claim in claims if claim is not None]
        if not claims:
            raise ValueError("A content slide must have at least one real claim")

        source_lookup = evidence_lookup or {}
        claim_records = []
        for claim in claims:
            mappings = []
            for span in claim.numeric_spans:
                evidence = source_lookup.get(span.evidence_id)
                mappings.append({
                    "numeric_id": span.numeric_id,
                    "value": span.value,
                    "char_span_in_claim": [span.char_start, span.char_end],
                    "evidence_id": span.evidence_id,
                    "verification": span.verification_status,
                    "source": getattr(evidence, "source_file", None),
                    "location": getattr(evidence, "exact_location", None),
                    "passage": getattr(evidence, "exact_passage", None),
                })
            claim_records.append({
                "claim_id": claim.claim_id,
                "statement": claim.statement,
                "atomic_numeric_mapping": mappings,
                "evidence_ids": claim.evidence_ids,
                "visible_citation": claim.visible_citation,
            })

        verification = {"schema_version": 2, "claim_count": len(claim_records), "claims": claim_records}
        verification["integrity"] = self._integrity(verification)
        notes = slide.notes_slide.notes_text_frame
        if notes is None:
            raise RuntimeError("The PowerPoint template does not support auditable speaker notes")
        notes.text = json.dumps({"citedeck_verification": verification}, indent=2, ensure_ascii=False)

    def extract_invisible_metadata(self, slide):
        try:
            notes = slide.notes_slide.notes_text_frame
            if notes is None:
                return None
            payload = json.loads(notes.text)
            return payload if isinstance(payload, dict) and "citedeck_verification" in payload else None
        except (AttributeError, json.JSONDecodeError, KeyError, TypeError):
            return None

    def create_professional_slide(self, prs, title, statement, visible_citation, atomic_claim):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        if slide.shapes.title is not None:
            slide.shapes.title.text = title
        if len(slide.placeholders) > 1:
            slide.placeholders[1].text = statement
        footer = slide.shapes.add_textbox(Inches(0.45), prs.slide_height - Inches(0.55), prs.slide_width - Inches(0.9), Inches(0.3))
        footer.text_frame.text = visible_citation
        footer.text_frame.paragraphs[0].font.size = Pt(10)
        self.add_invisible_metadata_to_slide(slide, atomic_claim)
        return slide
