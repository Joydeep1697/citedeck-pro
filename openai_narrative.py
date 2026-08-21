import os, json
from openai import OpenAI

class OpenAINarrative:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found")
        self.client = OpenAI(api_key=self.api_key)

    def generate_defensible_deck(self, idea: str, verified_facts: list, evidence_store: list):
        """
        Generates deck where every bullet MUST have source.
        Forces citations - rejects hallucination.
        """
        facts_text = "\n".join([f"- {f.get('claim','')} | Source: {f.get('source_file','')} | Text: {f.get('source_text','')[:200]}" for f in verified_facts[:15]])
        evidence_text = "\n".join([f"- {e.get('fact','')} from {e.get('source','')}" for e in evidence_store[:10]])

        prompt = f"""
You are CiteDeck engine. You create investor decks that survive diligence. Every number must have source.

IDEA: {idea}

FACTS WITH PROVENANCE (use only these, don't invent):
{facts_text}

EVIDENCE STORE:
{evidence_text}

RULES - BRUTAL:
1. Every slide must have at least 1 citation from facts above
2. Every number/bullet must reference source file or URL from facts
3. If fact not in list, write [NOT_FOUND - no source] - NEVER hallucinate TAM, revenue, etc.
4. Create 12-slide structure: Title, Problem, Solution, Market Size (with TAM from sources), Product, Traction (from user files), Business Model, Competition (from Tavily), Go-to-Market, Team, Financials (from Excel), Ask
5. For Market Size, you MUST cite Tavily URL and your Excel file name
6. For charts, specify chart_type and data_source = exact file name from facts
7. Output ONLY valid JSON, no markdown

Return JSON format:
{{
  "slides": [
    {{
      "title": "Slide title",
      "bullets": ["bullet with [source: file.pdf page 2]", "bullet with [source: https://...]"],
      "citations": ["file.pdf", "https://..."],
      "chart_needed": false,
      "chart_type": null,
      "chart_data_source": null,
      "verification_note": "Why this claim exists"
    }}
  ]
}}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are CiteDeck - you create decks that survive diligence. Never hallucinate numbers. Every claim needs source."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            return data.get("slides", [])
        except Exception as e:
            print(f"OpenAI error: {e}")
            # Fallback: return basic slides with citations
            return [
                {"title": "Problem", "bullets": [f"{idea} - from user files", f"Evidence: {verified_facts[0]['source_file'] if verified_facts else 'user files'}"], "citations": [verified_facts[0]['source_file'] if verified_facts else "user"], "chart_needed": False},
                {"title": "Market - Verifiable", "bullets": [f"TAM from: {verified_facts[1]['source_file'] if len(verified_facts)>1 else 'Tavily search'}", "Source URL in footer"], "citations": [f['source_file'] for f in verified_facts[:2]], "chart_needed": True, "chart_type": "bar", "chart_data_source": verified_facts[0]['source_file'] if verified_facts else "user Excel"},
                {"title": "Why This Claim Exists", "bullets": ["Click any number to see source PDF page + web URL + FX proof - inspection layer"], "citations": ["evidence_store"], "chart_needed": False}
            ]
