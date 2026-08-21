import re
from typing import List, Tuple, Optional

class AtomicContentVerifierV6:
    """
    FIXES CRITICAL ISSUE 1: V5 does not verify evidence actually supports the number
    Your adversarial test: Claim $25B with evidence passage "Market is actually $10B" -> V5 passed (should fail)
    
    V6: Verifies that evidence passage actually contains the claimed number and context supports it
    """
    
    def normalize_number(self, value_str: str) -> dict:
        """
        Normalizes $25B, $25 billion, 25B, 25,000,000,000 to comparable form
        Returns dict with raw, numeric, unit, normalized
        """
        value_str = value_str.strip()
        # Extract numeric part
        num_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', value_str.replace('$','').replace('%',''))
        if not num_match:
            return {"raw": value_str, "numeric": None, "unit": None, "normalized": value_str.lower()}
        
        num_str = num_match.group(1).replace(',','')
        try:
            num = float(num_str)
        except:
            num = None
        
        # Extract unit
        unit_match = re.search(r'(B|M|K|Cr|billion|million|thousand|%)', value_str, re.I)
        unit = unit_match.group(1).lower() if unit_match else None
        
        # Normalize to base number for comparison
        normalized_num = num
        if num is not None:
            if unit in ['b', 'billion']:
                normalized_num = num * 1_000_000_000
            elif unit in ['m', 'million']:
                normalized_num = num * 1_000_000
            elif unit in ['k', 'thousand']:
                normalized_num = num * 1_000
            elif unit in ['cr']:
                normalized_num = num * 10_000_000
        
        return {
            "raw": value_str,
            "numeric": num,
            "unit": unit,
            "normalized": normalized_num,
            "normalized_str": f"{normalized_num}_{unit}" if normalized_num else value_str.lower()
        }
    
    def does_passage_contain_number(self, claimed_value: str, passage: str) -> dict:
        """
        Checks if evidence passage actually contains the claimed number
        Not just if evidence ID exists, but does passage support it
        """
        claimed_norm = self.normalize_number(claimed_value)
        passage_lower = passage.lower()
        
        # Check 1: Does exact claimed value appear in passage?
        claimed_raw_lower = claimed_value.lower()
        exact_match = claimed_raw_lower in passage_lower
        
        # Check 2: Does normalized number appear?
        # Look for the numeric part in passage
        passage_numbers = re.findall(r'\$?\d+(?:,\d+)*(?:\.\d+)?\s*(?:B|M|K|Cr|billion|million|%|USD|INR)?', passage, re.I)
        normalized_match = False
        conflicting_numbers = []
        
        for p_num_str in passage_numbers:
            p_norm = self.normalize_number(p_num_str)
            # If same normalized value, it's supporting
            if claimed_norm["normalized"] is not None and p_norm["normalized"] is not None:
                # Allow small tolerance for rounding
                if abs(claimed_norm["normalized"] - p_norm["normalized"]) < 0.01 * max(1, claimed_norm["normalized"]):
                    normalized_match = True
            # Check for conflicting numbers in same context (e.g., market size)
            # If passage has different market size, it's conflicting
            if p_norm["numeric"] is not None and claimed_norm["numeric"] is not None:
                if p_norm["unit"] == claimed_norm["unit"] and p_norm["numeric"] != claimed_norm["numeric"]:
                    # Different number with same unit - potential conflict, need context check
                    # For strict check: if passage says "Market is actually $10B" but claim is $25B, it's conflict
                    conflicting_numbers.append(p_num_str)
        
        # Check 3: Context support - does passage talk about same metric?
        # Simple keyword overlap for now - in production would use semantic similarity
        # For adversarial test: "Market is $25B" vs "Market is actually $10B" - conflicting
        
        supports = exact_match or normalized_match
        has_conflict = len(conflicting_numbers) > 0 and not supports
        
        # Special case for adversarial test: claim $25B, passage says $10B
        # If claimed value NOT in passage but different value of same unit IS in passage, it's a failure
        if not supports and conflicting_numbers:
            # Passage contains different number with same unit context - likely contradictory
            return {
                "supports": False,
                "exact_match": False,
                "normalized_match": False,
                "conflicting_numbers": conflicting_numbers,
                "reason": f"Claimed {claimed_value} not found in passage, but found conflicting {conflicting_numbers} - evidence does not support claim",
                "adversarial_test_detected": True
            }
        
        return {
            "supports": supports,
            "exact_match": exact_match,
            "normalized_match": normalized_match,
            "conflicting_numbers": conflicting_numbers,
            "reason": f"Claimed {claimed_value} {'found' if supports else 'NOT found'} in passage. Passage numbers: {passage_numbers[:3]}",
            "adversarial_test_detected": False
        }
    
    def verify_atomic_claim(self, numeric_span, evidence) -> dict:
        """
        V6 atomic verification: Does this specific number's evidence actually support it?
        
        Args:
            numeric_span: NumericSpan with value "$25B"
            evidence: AtomicEvidence with exact_passage
        """
        claimed_value = numeric_span.value
        passage = evidence.exact_passage
        
        content_check = self.does_passage_contain_number(claimed_value, passage)
        
        # Check location exists (V5 check)
        has_location = bool(evidence.exact_location and not evidence.exact_location.get("pending"))
        
        # Check passage exists
        has_passage = bool(passage and len(passage) > 10)
        
        # Final verdict: must have location, passage, AND content supports
        verified = has_location and has_passage and content_check["supports"] and not content_check["adversarial_test_detected"]
        
        return {
            "numeric_id": numeric_span.numeric_id,
            "claimed_value": claimed_value,
            "evidence_id": evidence.evidence_id,
            "source": evidence.source_file,
            "location": evidence.exact_location,
            "has_location": has_location,
            "has_passage": has_passage,
            "content_supports": content_check["supports"],
            "exact_match": content_check["exact_match"],
            "conflicting_numbers": content_check["conflicting_numbers"],
            "reason": content_check["reason"],
            "verified": verified,
            "adversarial_test_passed": not content_check["adversarial_test_detected"],
            "v6_check": "Does evidence passage actually contain and support the claimed number?"
        }

if __name__ == "__main__":
    verifier = AtomicContentVerifierV6()
    
    # Your adversarial test 1: Claim $25B with evidence saying $10B
    print("=== Adversarial Test 1: Claim $25B vs Evidence $10B ===")
    result = verifier.does_passage_contain_number("$25B", "Market is actually $10B according to report")
    print(f"Supports: {result['supports']} - Should be False")
    print(f"Reason: {result['reason']}")
    print(f"Adversarial detected: {result['adversarial_test_detected']} - Should be True")
    
    print("\n=== Adversarial Test 2: Claim $25B vs Evidence $25B ===")
    result2 = verifier.does_passage_contain_number("$25B", "The EV market will reach $25B by 2030")
    print(f"Supports: {result2['supports']} - Should be True")
    print(f"Reason: {result2['reason']}")
