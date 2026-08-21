"""Bounded Tavily research that retains source URLs and source passages."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os


LOGGER = logging.getLogger(__name__)


class TavilyResearch:
    def __init__(self, api_key: str | None = None, client=None) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if client is None:
            if not self.api_key:
                raise ValueError("TAVILY_API_KEY is not configured")
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.api_key)
        self.client = client

    def research_gap(self, query: str, max_results: int = 5) -> dict:
        try:
            response = self.client.search(query=query[:400], search_depth="advanced", include_answer=False, include_raw_content=False, max_results=min(max_results, 8))
        except Exception as exc:
            LOGGER.warning("Research request failed for a deck evidence query: %s", type(exc).__name__)
            return {"query": query, "error": "Research provider unavailable", "results": [], "citations_ready": False}

        results = []
        for item in response.get("results", []):
            url, passage = item.get("url"), str(item.get("content") or "").strip()
            if url and passage:
                results.append({"claim": passage[:300], "url": url, "source_text": passage[:1000], "score": item.get("score"), "published_date": item.get("published_date"), "verification_status": "WEB_RETRIEVED", "can_use_in_deck": True})
        return {"query": query, "results": results, "citations_ready": bool(results)}

    def research_deck_gaps(self, idea: str) -> dict:
        year = datetime.now(timezone.utc).year
        queries = [f"{idea} total addressable market size {year}", f"{idea} market growth rate industry report", f"{idea} competitors pricing"]
        return {query: self.research_gap(query) for query in queries}
