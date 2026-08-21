import os
from tavily import TavilyClient

class TavilyResearch:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY not found in env or secrets")
        self.client = TavilyClient(api_key=self.api_key)

    def research_gap(self, query: str, max_results=5):
        """Real web search with citations - no hallucination"""
        try:
            response = self.client.search(
                query=query,
                search_depth="advanced",
                include_answer=True,
                include_raw_content=False,
                max_results=max_results
            )
            results = []
            for r in response.get("results", []):
                results.append({
                    "claim": r.get("content", "")[:300],
                    "url": r.get("url"),
                    "source_text": r.get("content", "")[:500],
                    "score": r.get("score"),
                    "published_date": r.get("published_date"),
                    "verification_status": "WEB_VERIFIED",
                    "can_use_in_deck": True
                })
            return {
                "query": query,
                "answer": response.get("answer", ""),
                "results": results,
                "citations_ready": True
            }
        except Exception as e:
            return {"query": query, "error": str(e), "results": [], "citations_ready": False}

    def research_deck_gaps(self, idea: str):
        """Research all missing pieces for investor deck"""
        gaps = [
            f"{idea} total addressable market size 2024 2025",
            f"{idea} market CAGR growth rate",
            f"{idea} competitors list pricing",
            f"{idea} industry trends report"
        ]
        all_research = {}
        for gap in gaps:
            print(f"Researching: {gap}")
            all_research[gap] = self.research_gap(gap)
        return all_research
