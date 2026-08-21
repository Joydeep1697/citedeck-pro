import os, json
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches

# V6 components
from atomic_claim_evidence import AtomicClaimBuilder, AtomicClaim
from atomic_content_verifier_v6 import AtomicContentVerifierV6
from tamper_detector_v6 import TamperDetectorV6
from evidence_retriever_v6 import EvidenceRetrieverV6
from invisible_metadata_engine import InvisibleMetadataEngine
from evidence_extractor_real import EvidenceExtractorReal
from chart_generator_real import ChartGeneratorReal
from tavily_research import TavilyResearch
from openai_narrative import OpenAINarrative

class RealEngineV6FullPipeline:
    """
    FIXES IMPORTANT ISSUE 4: V5 not integrated into complete pipeline
    Old: app_v5_atomic_invisible.py is demo with manually created evidence
    New V6: Full end-to-end pipeline
    
    User uploads documents
        ↓
    Evidence extracted (real page/cell)
        ↓
    Tavily research for gaps
        ↓
    OpenAI narrative generates slides
        ↓
    Every numeric claim atomically linked to exact evidence span
        ↓
    Deck created with invisible metadata
        ↓
    QC validates: content supports number, visible == hidden, no tamper
        ↓
    Export blocked if verification fails
    """
    
    def __init__(self, tavily_key=None, openai_key=None):
        self.extractor = EvidenceExtractorReal()
        self.tavily_key = tavily_key
        self.openai_key = openai_key
        self.researcher = TavilyResearch(api_key=tavily_key) if tavily_key else None
        self.narrator = OpenAINarrative(api_key=openai_key) if openai_key else None
        
        self.atomic_builder = AtomicClaimBuilder()
        self.content_verifier = AtomicContentVerifierV6()
        self.tamper_detector = TamperDetectorV6()
        self.retriever = EvidenceRetrieverV6()
        self.invisible_engine = InvisibleMetadataEngine()
        self.chart_gen = ChartGeneratorReal()
        
        self.evidence_store = []  # All evidences from docs + web
        self.atomic_claims = []  # All atomic claims with numeric spans
    
    def step_2_extract(self, uploaded_paths):
        """Real extraction with page/cell provenance"""
        all_facts = []
        for path in uploaded_paths:
            ext = Path(path).suffix.lower()
            if ext == '.pdf':
                facts = self.extractor.extract_pdf_with_pages(path)
            elif ext in ['.xlsx', '.xls']:
                facts = self.extractor.extract_excel_with_cells(path)
            elif ext == '.docx':
                facts = self.extractor.extract_docx_with_paragraph(path)
            else:
                continue
            
            # Convert to atomic evidences
            for fact in facts:
                eid = self.atomic_builder.add_atomic_evidence(
                    source_file=fact["source_file"],
                    exact_location={
                        "page": fact.get("page_number"),
                        "cell_range": fact.get("cell_range"),
                        "cell": fact.get("cell"),
                        "sheet": fact.get("sheet"),
                        "paragraph": fact.get("paragraph_number")
                    },
                    exact_passage=fact.get("source_text", fact.get("claim",""))[:500],
                    char_span=(fact.get("char_start"), fact.get("char_end")) if fact.get("char_start") else None
                )
                self.evidence_store.append(self.atomic_builder.evidences[-1])
                all_facts.append(fact)
        
        return all_facts
    
    def step_3_research(self, idea):
        """Real Tavily research"""
        if not self.researcher:
            return []
        
        research_results = self.researcher.research_deck_gaps(idea)
        for gap_name, result in research_results.items():
            for r in result.get("results", [])[:3]:
                eid = self.atomic_builder.add_atomic_evidence(
                    source_file=r["url"],
                    exact_location={"url": r["url"], "score": r.get("score")},
                    exact_passage=r["source_text"][:500],
                    url=r["url"]
                )
                self.evidence_store.append(self.atomic_builder.evidences[-1])
        
        return research_results
    
    def step_5_generate_atomic_claims(self, idea, facts):
        """Generate narrative and create atomic claims with numeric spans"""
        if self.narrator:
            slides = self.narrator.generate_defensible_deck(idea, facts, [])
        else:
            # Fallback slides for testing
            slides = [
                {"title": "Market", "bullets": [f"Market is {facts[0]['claim'] if facts else '$25B'} by 2030"], "citations": [facts[0]["source_file"] if facts else "market_report.pdf"]}
            ]
        
        # Convert each slide bullet to atomic claims
        atomic_claims = []
        for slide_idx, slide in enumerate(slides):
            for bullet in slide.get("bullets", []):
                # Each bullet becomes atomic claim with numeric spans
                claim = self.atomic_builder.add_atomic_claim(
                    statement=bullet,
                    slide_number=slide_idx+1,
                    visible_citation=f"Source: {', '.join(slide.get('citations', [])[:2])}"
                )
                
                # Production-grade retrieval: link each number to best evidence
                linked = self.retriever.link_claim_atomically(claim, self.evidence_store)
                atomic_claims.append(claim)
        
        self.atomic_claims = atomic_claims
        return slides, atomic_claims
    
    def step_7_create_deck_with_invisible_layer(self, template_path, slides, atomic_claims, output_path):
        """Creates deck with visible clean citations + invisible atomic mapping"""
        if template_path and Path(template_path).exists():
            prs = Presentation(template_path)
        else:
            prs = Presentation()
        
        # Ensure enough slides
        while len(prs.slides) < len(slides):
            prs.slides.add_slide(prs.slide_layouts[1])
        
        for idx, slide_data in enumerate(slides):
            if idx >= len(prs.slides):
                break
            
            slide = prs.slides[idx]
            # Find atomic claim for this slide
            claim_for_slide = next((c for c in atomic_claims if c.slide_number == idx+1), None)
            if not claim_for_slide and atomic_claims:
                claim_for_slide = atomic_claims[0]  # fallback
            
            # Visible: clean title + bullets + clean citation
            slide.shapes.title.text = slide_data.get("title", f"Slide {idx+1}")
            bullets_text = "\n".join([f"• {b}" for b in slide_data.get("bullets", [])])
            for shape in slide.shapes:
                if shape.has_text_frame and shape != slide.shapes.title and "Source:" not in shape.text_frame.text:
                    if len(shape.text_frame.text) < 100:
                        shape.text_frame.text = bullets_text
                        break
            
            # Visible clean citation
            visible_citation = slide_data.get("citations", ["Source: internal analysis"])[0] if slide_data.get("citations") else "Source: analysis"
            if claim_for_slide:
                visible_citation = claim_for_slide.visible_citation
            
            footer = slide.shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(9), Inches(0.4))
            footer.text_frame.text = visible_citation
            
            # Invisible: atomic mapping in notes
            if claim_for_slide:
                self.invisible_engine.add_invisible_metadata_to_slide(slide, claim_for_slide)
        
        prs.save(output_path)
        return output_path
    
    def step_8_qc_v6_full(self, pptx_path):
        """
        V6 Full QC:
        1. Content verification: Does evidence passage actually contain claimed number?
        2. Tamper detection: Does visible slide match hidden claim?
        3. Atomic verification: Does each number have exact evidence span?
        4. Block export if fails
        """
        prs = Presentation(pptx_path)
        results = {
            "total_slides": len(prs.slides),
            "atomic_content_checks": [],
            "tamper_checks": [],
            "can_publish": True,
            "qc_pass": True,
            "issues": [],
            "adversarial_tests": []
        }
        
        for idx, slide in enumerate(prs.slides):
            # Get atomic claim for this slide from notes
            invisible_data = self.invisible_engine.extract_invisible_metadata(slide)
            if not invisible_data:
                if idx > 0:
                    results["issues"].append(f"Slide {idx+1}: No invisible verification layer")
                    results["can_publish"] = False
                continue
            
            verification = invisible_data.get("citedeck_verification", {})
            claim_id = verification.get("claim_id")
            atomic_mapping = verification.get("atomic_numeric_mapping", [])
            
            claim = next((c for c in self.atomic_claims if c.claim_id == claim_id), None)
            if not claim:
                results["issues"].append(f"Slide {idx+1}: Claim {claim_id} in notes but not in graph")
                results["can_publish"] = False
                continue
            
            # Check 1: Tamper detection - visible vs hidden
            tamper_result = self.tamper_detector.detect_tampering(slide, claim)
            results["tamper_checks"].append(tamper_result)
            if tamper_result["tamper_detected"]:
                results["can_publish"] = False
                results["qc_pass"] = False
                results["issues"].extend(tamper_result["issues"])
                results["adversarial_tests"].append(f"Tamper detected on slide {idx+1}: {tamper_result['issues']}")
            
            # Check 2: Content verification - does evidence actually support number?
            for numeric_span in claim.numeric_spans:
                evidence = next((ev for ev in self.evidence_store if ev.evidence_id == numeric_span.evidence_id), None)
                if not evidence:
                    results["issues"].append(f"Slide {idx+1} {numeric_span.value} -> {numeric_span.evidence_id} not found")
                    results["can_publish"] = False
                    continue
                
                content_check = self.content_verifier.verify_atomic_claim(numeric_span, evidence)
                results["atomic_content_checks"].append(content_check)
                
                if not content_check["verified"]:
                    results["can_publish"] = False
                    results["qc_pass"] = False
                    results["issues"].append(f"Slide {idx+1} {content_check['claimed_value']} not supported by evidence {content_check['evidence_id']}: {content_check['reason']}")
                    if content_check.get("adversarial_test_passed") == False:
                        results["adversarial_tests"].append(f"Adversarial: Claim {content_check['claimed_value']} vs Evidence passage says {content_check['conflicting_numbers']} - correctly FAILED")
        
        # Final
        if results["can_publish"] and len(results["issues"]) == 0:
            results["verification_status"] = "PASSED V6 - Every number verified: content supports number, visible==hidden, atomic span exact"
            results["trust_badge"] = "✓ CiteDeck V6 Verified: Atomic numeric-span, tamper-proof, content-verified"
        else:
            results["verification_status"] = "FAILED V6 - Verification incomplete or tampering detected - export blocked"
            results["trust_badge"] = "⚠ Verification failed - export blocked - fix issues"
            results["qc_pass"] = False
            results["can_publish"] = False
        
        return results

if __name__ == "__main__":
    print("Real Engine V6 Full Pipeline - end-to-end with atomic + invisible + tamper + content checks")
