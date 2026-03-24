"""arXiv monitoring — scans for new bioinformatics preprints."""

from __future__ import annotations

import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any

from bioopenclaw.mcp_servers.scout_agent.config import get_config

logger = logging.getLogger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


async def scan_arxiv_papers(
    query: str | None = None,
    categories: list[str] | None = None,
    days_back: int = 7,
    max_results: int = 30,
) -> dict[str, Any]:
    """Search arXiv for recent preprints in bioinformatics-related categories.

    Uses the arXiv Atom API.  Filters results to papers submitted within
    *days_back* days.
    """
    cfg = get_config()
    if categories is None:
        categories = list(cfg.arxiv_categories)

    cat_query = " OR ".join(f"cat:{c}" for c in categories)

    if query:
        search_query = f"({cat_query}) AND all:{query}"
    else:
        search_query = cat_query

    params = urllib.parse.urlencode({
        "search_query": search_query,
        "start": 0,
        "max_results": max_results * 2,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })

    url = f"{ARXIV_API_URL}?{params}"
    logger.info("arXiv query: %s", url)

    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        papers: list[dict[str, Any]] = []

        for entry in root.findall(f"{ATOM_NS}entry"):
            published_str = _text(entry, f"{ATOM_NS}published")
            if not published_str:
                continue

            try:
                published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            if published < cutoff:
                continue

            arxiv_id = _text(entry, f"{ATOM_NS}id", "").split("/abs/")[-1]
            paper_cats = [
                c.get("term", "")
                for c in entry.findall(f"{ATOM_NS}category")
            ]

            authors = [
                _text(a, f"{ATOM_NS}name")
                for a in entry.findall(f"{ATOM_NS}author")
            ]

            papers.append({
                "arxiv_id": arxiv_id,
                "title": _text(entry, f"{ATOM_NS}title", "").replace("\n", " ").strip(),
                "authors": authors[:5],
                "summary": _text(entry, f"{ATOM_NS}summary", "").replace("\n", " ").strip()[:400],
                "published": published.isoformat(),
                "categories": paper_cats,
                "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            })

        papers = papers[:max_results]

        logger.info("arXiv scan complete: %d papers found", len(papers))
        return {
            "success": True,
            "query": {
                "search_query": search_query,
                "categories": categories,
                "days_back": days_back,
            },
            "total_found": len(papers),
            "papers": papers,
        }

    except Exception as e:
        logger.error("arXiv scan failed: %s", e)
        return {"success": False, "error": str(e)}


def _text(element: ET.Element, tag: str, default: str = "") -> str:
    """Safely extract text from an XML element."""
    child = element.find(tag)
    return (child.text or default) if child is not None else default
