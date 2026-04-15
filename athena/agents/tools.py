"""Tool functions available to SRE subagents.

These are @tool-decorated functions registered in subagents.yaml
and resolved by load_subagents() in pipeline.py.
"""

import os
from typing import Literal

from langchain_core.tools import tool


@tool
def web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news"] = "general",
) -> dict:
    """Search the web for documentation, CVEs, or troubleshooting guides.

    Args:
        query: Specific search query (be detailed)
        max_results: Number of results to return (default: 5)
        topic: "general" for docs/guides, "news" for recent incidents/CVEs

    Returns:
        Search results with titles, URLs, and content excerpts.
    """
    try:
        from tavily import TavilyClient

        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return {"error": "TAVILY_API_KEY not set — web search unavailable"}

        client = TavilyClient(api_key=api_key)
        return client.search(query, max_results=max_results, topic=topic)
    except Exception as e:
        return {"error": f"Search failed: {e}"}
