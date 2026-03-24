"""PubMed literature search — migrated from legacy mcp_server/server.py."""

from __future__ import annotations

import logging
import os
from typing import Any

from bioopenclaw.mcp_servers.research_agent.config import get_config

logger = logging.getLogger(__name__)


async def search_pubmed(
    query: str,
    max_results: int = 20,
    email: str | None = None,
    database: str = "pubmed",
    sort_by: str = "relevance",
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Search PubMed/NCBI for biomedical literature.

    Uses the NCBI Entrez E-utilities API via BioPython.
    """
    try:
        from Bio import Entrez
    except ImportError:
        return {"success": False, "error": "biopython not installed: pip install biopython"}

    cfg = get_config()
    email = email or cfg.entrez_email or os.environ.get("ENTREZ_EMAIL", "")
    if not email:
        return {
            "success": False,
            "error": "ENTREZ_EMAIL must be set (NCBI requires a contact email)",
        }

    Entrez.email = email
    api_key = cfg.ncbi_api_key or os.environ.get("NCBI_API_KEY", "")
    if api_key:
        Entrez.api_key = api_key

    search_query = query
    if date_from or date_to:
        date_filter = f" AND ({date_from or '1900'}[PDAT] : {date_to or '3000'}[PDAT])"
        search_query += date_filter

    logger.info("PubMed search: '%s' (db=%s, max=%d)", search_query, database, max_results)

    try:
        handle = Entrez.esearch(
            db=database,
            term=search_query,
            retmax=max_results,
            sort=sort_by,
        )
        search_results = Entrez.read(handle)
        handle.close()

        pmids = search_results.get("IdList", [])
        if not pmids:
            return {"success": True, "query": query, "total_found": 0, "papers": []}

        handle = Entrez.efetch(db=database, id=pmids, rettype="xml", retmode="xml")
        records = Entrez.read(handle)
        handle.close()

        papers = []
        for record in records.get("PubmedArticle", []):
            try:
                article = record["MedlineCitation"]["Article"]
                pmid = str(record["MedlineCitation"]["PMID"])
                title = str(article.get("ArticleTitle", ""))

                abstract = ""
                if "Abstract" in article:
                    abstract_texts = article["Abstract"].get("AbstractText", [])
                    if isinstance(abstract_texts, list):
                        abstract = " ".join(str(t) for t in abstract_texts)
                    else:
                        abstract = str(abstract_texts)

                authors = []
                if "AuthorList" in article:
                    for author in article["AuthorList"][:5]:
                        last = author.get("LastName", "")
                        fore = author.get("ForeName", "")
                        if last:
                            authors.append(f"{last} {fore}".strip())

                journal = ""
                pub_date = ""
                if "Journal" in article:
                    journal = str(article["Journal"].get("Title", ""))
                    journal_issue = article["Journal"].get("JournalIssue", {})
                    pub_date_info = journal_issue.get("PubDate", {})
                    pub_date = pub_date_info.get("Year", "")

                mesh_terms = []
                mesh_list = record.get("MedlineCitation", {}).get("MeshHeadingList", [])
                for mesh in mesh_list[:10]:
                    desc = mesh.get("DescriptorName", "")
                    if desc:
                        mesh_terms.append(str(desc))

                papers.append({
                    "pmid": pmid,
                    "title": title,
                    "authors": authors,
                    "journal": journal,
                    "year": pub_date,
                    "abstract": abstract[:500] + ("..." if len(abstract) > 500 else ""),
                    "mesh_terms": mesh_terms,
                    "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "doi_url": "",
                })
            except (KeyError, TypeError) as e:
                logger.debug("Error parsing PubMed record: %s", e)
                continue

        return {
            "success": True,
            "query": query,
            "database": database,
            "total_found": len(papers),
            "papers": papers,
        }
    except Exception as e:
        logger.error("PubMed search failed: %s", e)
        return {"success": False, "error": str(e)}
