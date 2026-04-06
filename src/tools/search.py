"""
ArXiv Search Tool — Tool 1 for the ReAct Agent.

Provides two functions:
    - search_arxiv(query): Search for papers on ArXiv by keyword.
    - get_paper_abstract(paper_id): Fetch the full abstract of a specific paper.

Data source: ArXiv API (http://export.arxiv.org/api/query)
Fallback: Mock JSON file for offline/demo usage.
"""

import os
import json
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional


# ArXiv API base URL
ARXIV_API_URL = "http://export.arxiv.org/api/query"

# Path to optional mock data file (for offline testing)
MOCK_DATA_PATH = os.path.join(
    os.path.dirname(__file__), "mock_arxiv_data.json"
)


def _parse_arxiv_entry(entry: ET.Element, ns: Dict[str, str]) -> Dict[str, str]:
    """Parse a single ArXiv Atom entry into a clean dictionary.

    Args:
        entry: An XML Element representing one ArXiv paper.
        ns: XML namespace mapping.

    Returns:
        Dict with keys: id, title, authors, summary, published, link.
    """
    # Extract paper ID from the full URL
    raw_id = entry.find("atom:id", ns)
    paper_id = raw_id.text.split("/abs/")[-1] if raw_id is not None else "N/A"

    title = entry.find("atom:title", ns)
    title_text = " ".join(title.text.split()) if title is not None else "N/A"

    summary = entry.find("atom:summary", ns)
    summary_text = " ".join(summary.text.split()) if summary is not None else "N/A"

    published = entry.find("atom:published", ns)
    published_text = published.text[:10] if published is not None else "N/A"

    # Authors
    author_elements = entry.findall("atom:author/atom:name", ns)
    authors = [a.text for a in author_elements] if author_elements else ["N/A"]

    # Link to the paper
    link_el = entry.find("atom:link[@type='text/html']", ns)
    if link_el is None:
        link_el = entry.find("atom:link", ns)
    link = link_el.get("href", "N/A") if link_el is not None else "N/A"

    return {
        "id": paper_id,
        "title": title_text,
        "authors": ", ".join(authors),
        "summary": summary_text,
        "published": published_text,
        "link": link,
    }


MAX_PAPERS = 3  # Hard cap — agent processes at most this many papers per query


def search_arxiv(query: str, max_results: int = MAX_PAPERS) -> str:
    """Search for scientific papers on ArXiv by keyword.

    This tool queries the ArXiv API for papers matching the given search
    query and returns the top results with title, authors, and summary.

    Args:
        query: A search query string (e.g., "Alpha Momentum stock market").
        max_results: Maximum number of papers to return (capped at 3).

    Returns:
        A formatted string containing the search results, or an error
        message if the API call fails.
    """
    max_results = min(max_results, MAX_PAPERS)  # enforce hard cap
    # Try real API first
    try:
        # Use category filter for quantitative finance when query seems financial
        finance_keywords = [
            "momentum", "alpha", "stock", "factor", "investing",
            "portfolio", "trading", "market", "sharpe", "hedge",
        ]
        is_finance = any(kw in query.lower() for kw in finance_keywords)

        # Build query: search in title + abstract for better relevance
        terms = query.strip().split()
        if len(terms) > 1:
            # Multi-word: search for all terms in title OR all in abstract
            ti_part = " AND ".join([f"ti:{t}" for t in terms])
            abs_part = " AND ".join([f"abs:{t}" for t in terms])
            search_query = f"({ti_part}) OR ({abs_part})"
        else:
            search_query = f"ti:{query} OR abs:{query}"

        if is_finance:
            search_query = f"({search_query}) AND cat:q-fin*"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        response = requests.get(ARXIV_API_URL, params=params, timeout=15)
        response.raise_for_status()

        # Parse XML response
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(response.text)
        entries = root.findall("atom:entry", ns)

        if not entries:
            return f"No papers found on ArXiv for query: '{query}'."

        papers: List[Dict[str, str]] = []
        for entry in entries:
            papers.append(_parse_arxiv_entry(entry, ns))

        # Format output for the Agent
        result_lines = [f"Found {len(papers)} papers on ArXiv for '{query}':\n"]
        for i, paper in enumerate(papers, start=1):
            result_lines.append(
                f"[{i}] Title: {paper['title']}\n"
                f"    ID: {paper['id']}\n"
                f"    Authors: {paper['authors']}\n"
                f"    Published: {paper['published']}\n"
                f"    Summary: {paper['summary']}\n"
                f"    Link: {paper['link']}\n"
            )

        return "\n".join(result_lines)

    except requests.exceptions.RequestException as e:
        # Fallback to mock data if API fails
        return _fallback_mock_search(query, str(e))


def get_paper_abstract(paper_id: str) -> str:
    """Fetch the full abstract of a specific ArXiv paper by its ID.

    Args:
        paper_id: The ArXiv paper ID (e.g., "2401.12345" or "2401.12345v1").

    Returns:
        A formatted string with the paper's title, authors, and full abstract.
    """
    try:
        params = {"id_list": paper_id}
        response = requests.get(ARXIV_API_URL, params=params, timeout=15)
        response.raise_for_status()

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(response.text)
        entries = root.findall("atom:entry", ns)

        if not entries:
            return f"No paper found with ID: '{paper_id}'."

        entry = entries[0]

        # Check if it's a valid paper (ArXiv returns a default entry for invalid IDs)
        title_el = entry.find("atom:title", ns)
        title = " ".join(title_el.text.split()) if title_el is not None else ""
        if title.lower() == "error":
            return f"No paper found with ID: '{paper_id}'."

        summary_el = entry.find("atom:summary", ns)
        full_abstract = " ".join(summary_el.text.split()) if summary_el is not None else "N/A"

        author_elements = entry.findall("atom:author/atom:name", ns)
        authors = ", ".join(a.text for a in author_elements) if author_elements else "N/A"

        published_el = entry.find("atom:published", ns)
        published = published_el.text[:10] if published_el is not None else "N/A"

        return (
            f"Paper: {title}\n"
            f"Authors: {authors}\n"
            f"Published: {published}\n"
            f"Abstract: {full_abstract}\n"
            f"Link: https://arxiv.org/abs/{paper_id}\n"
        )

    except requests.exceptions.RequestException as e:
        return f"Error fetching paper {paper_id}: {e}"


def _fallback_mock_search(query: str, error_msg: str) -> str:
    """Return mock data when the ArXiv API is unavailable.

    Args:
        query: The original search query.
        error_msg: The error message from the failed API call.

    Returns:
        Mock results or an error message.
    """
    if os.path.exists(MOCK_DATA_PATH):
        with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
            mock_data = json.load(f)

        results = [
            p for p in mock_data
            if query.lower() in p.get("title", "").lower()
            or query.lower() in p.get("summary", "").lower()
        ]

        if results:
            lines = [f"[MOCK DATA] Found {len(results)} papers for '{query}':\n"]
            for i, p in enumerate(results[:3], start=1):
                lines.append(
                    f"[{i}] Title: {p['title']}\n"
                    f"    ID: {p.get('id', 'N/A')}\n"
                    f"    Authors: {p.get('authors', 'N/A')}\n"
                    f"    Summary: {p.get('summary', 'N/A')}\n"
                    f"    Link: https://arxiv.org/abs/{p.get('id', 'N/A')}\n"
                )
            return "\n".join(lines)

    return (
        f"ArXiv API is currently unavailable ({error_msg}). "
        f"No mock data found for query: '{query}'."
    )


# ── Tool Registry Entry ─────────────────────────────────────────────────
# These dicts are what the ReAct Agent uses to discover and call tools.

SEARCH_ARXIV_TOOL = {
    "name": "search_arxiv",
    "description": (
        "Search for scientific papers on ArXiv by keyword. "
        "Parameter: query (string) — the search keywords (e.g., 'momentum stock market'). "
        "Call format: search_arxiv(query=\"your search terms\"). "
        "Returns at most 3 papers with title, ID, authors, published date, and summary. "
        "You must process ALL papers returned (up to 3) through the full workflow."
    ),
    "function": search_arxiv,
}

GET_PAPER_ABSTRACT_TOOL = {
    "name": "get_paper_abstract",
    "description": (
        "Fetch the full abstract of a specific ArXiv paper by its ArXiv ID. "
        "Parameter: paper_id (string) — the ArXiv ID (e.g., '2401.12345'). "
        "Call format: get_paper_abstract(paper_id=\"2401.12345\"). "
        "Returns the paper's title, authors, published date, and full abstract text."
    ),
    "function": get_paper_abstract,
}
