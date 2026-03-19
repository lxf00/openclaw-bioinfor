"""Intelligent dataset search — queries GEO, TCGA, and CellxGene in parallel."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from bioopenclaw.mcp_servers.data_agent.config import get_config

logger = logging.getLogger(__name__)


async def _search_geo(
    keywords: list[str],
    organism: str,
    data_type: str,
    min_samples: int,
    max_results: int,
) -> list[dict[str, Any]]:
    """Search GEO via NCBI Entrez esearch + esummary."""
    try:
        from Bio import Entrez
    except ImportError:
        logger.warning("biopython not installed, skipping GEO search")
        return []

    cfg = get_config()
    email = cfg.entrez_email or os.environ.get("ENTREZ_EMAIL", "")
    if not email:
        return []

    Entrez.email = email
    api_key = cfg.ncbi_api_key or os.environ.get("NCBI_API_KEY", "")
    if api_key:
        Entrez.api_key = api_key

    query_parts = keywords.copy()
    if organism:
        query_parts.append(f'"{organism}"[Organism]')
    if data_type:
        type_map = {
            "scRNA-seq": "single cell RNA-seq",
            "bulk-RNA-seq": "RNA-seq",
            "spatial": "spatial transcriptomics",
            "CITE-seq": "CITE-seq",
            "ATAC-seq": "ATAC-seq",
        }
        mapped = type_map.get(data_type, data_type)
        query_parts.append(f'"{mapped}"')

    query = " AND ".join(query_parts)
    logger.info("GEO search query: %s", query)

    try:
        handle = Entrez.esearch(db="gds", term=query, retmax=max_results * 2)
        search_results = Entrez.read(handle)
        handle.close()

        ids = search_results.get("IdList", [])
        if not ids:
            return []

        handle = Entrez.esummary(db="gds", id=",".join(ids[:max_results]))
        summaries = Entrez.read(handle)
        handle.close()

        results = []
        for item in summaries:
            try:
                n_samples = int(item.get("n_samples", 0))
                if n_samples < min_samples:
                    continue
                results.append({
                    "source": "GEO",
                    "id": f"GSE{item.get('GSE', '')}",
                    "title": str(item.get("title", "")),
                    "organism": str(item.get("taxon", "")),
                    "sample_count": n_samples,
                    "platform": str(item.get("GPL", "")),
                    "summary": str(item.get("summary", ""))[:300],
                    "date": str(item.get("PDAT", "")),
                    "geo_url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE{item.get('GSE', '')}",
                })
            except (KeyError, TypeError, ValueError):
                continue

        return results[:max_results]
    except Exception as e:
        logger.error("GEO search failed: %s", e)
        return []


async def _search_tcga(
    keywords: list[str],
    organism: str,
    data_type: str,
    min_samples: int,
    max_results: int,
) -> list[dict[str, Any]]:
    """Search TCGA via GDC API."""
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed, skipping TCGA search")
        return []

    if organism and "homo sapiens" not in organism.lower():
        return []

    gdc_url = "https://api.gdc.cancer.gov/projects"

    keyword_str = " ".join(keywords).lower()
    tissue_map = {
        "breast": "TCGA-BRCA",
        "lung": ["TCGA-LUAD", "TCGA-LUSC"],
        "liver": "TCGA-LIHC",
        "colon": "TCGA-COAD",
        "brain": ["TCGA-GBM", "TCGA-LGG"],
        "kidney": ["TCGA-KIRC", "TCGA-KIRP"],
        "prostate": "TCGA-PRAD",
        "ovarian": "TCGA-OV",
        "pancreas": "TCGA-PAAD",
        "stomach": "TCGA-STAD",
        "bladder": "TCGA-BLCA",
        "thyroid": "TCGA-THCA",
        "melanoma": "TCGA-SKCM",
        "cervical": "TCGA-CESC",
        "endometrial": "TCGA-UCEC",
        "head": "TCGA-HNSC",
    }

    matched_projects: list[str] = []
    for tissue, projects in tissue_map.items():
        if tissue in keyword_str:
            if isinstance(projects, list):
                matched_projects.extend(projects)
            else:
                matched_projects.append(projects)

    try:
        params: dict[str, Any] = {
            "size": max_results,
            "fields": "project_id,name,primary_site,disease_type,summary.case_count,summary.file_count",
        }

        if matched_projects:
            filters = {
                "op": "in",
                "content": {
                    "field": "project_id",
                    "value": matched_projects,
                },
            }
            import json
            params["filters"] = json.dumps(filters)

        response = requests.get(gdc_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        results = []
        for hit in data.get("data", {}).get("hits", []):
            case_count = hit.get("summary", {}).get("case_count", 0)
            if case_count < min_samples:
                continue
            results.append({
                "source": "TCGA",
                "id": hit.get("project_id", ""),
                "title": hit.get("name", ""),
                "organism": "Homo sapiens",
                "sample_count": case_count,
                "platform": "Illumina",
                "summary": f"Primary site: {hit.get('primary_site', 'N/A')}, "
                           f"Disease: {hit.get('disease_type', 'N/A')}, "
                           f"Files: {hit.get('summary', {}).get('file_count', 0)}",
                "date": "",
                "gdc_url": f"https://portal.gdc.cancer.gov/projects/{hit.get('project_id', '')}",
            })

        return results[:max_results]
    except Exception as e:
        logger.error("TCGA search failed: %s", e)
        return []


async def _search_cellxgene(
    keywords: list[str],
    organism: str,
    data_type: str,
    min_samples: int,
    max_results: int,
) -> list[dict[str, Any]]:
    """Search CellxGene Census collections via REST API."""
    try:
        import requests
    except ImportError:
        return []

    api_url = "https://api.cellxgene.cziscience.com/curation/v1/collections"

    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        collections = response.json()

        keyword_str = " ".join(keywords).lower()

        results = []
        for coll in collections:
            title = coll.get("name", "")
            description = coll.get("description", "")
            combined_text = f"{title} {description}".lower()

            if not any(kw.lower() in combined_text for kw in keywords):
                continue

            datasets = coll.get("datasets", [])
            total_cells = sum(d.get("cell_count", 0) for d in datasets)

            org_match = True
            if organism:
                dataset_organisms = set()
                for d in datasets:
                    for org in d.get("organism", []):
                        dataset_organisms.add(org.get("label", "").lower())
                if dataset_organisms and organism.lower() not in dataset_organisms:
                    org_match = False

            if not org_match:
                continue

            results.append({
                "source": "CellxGene",
                "id": coll.get("collection_id", ""),
                "title": title,
                "organism": organism or "various",
                "sample_count": len(datasets),
                "platform": "various",
                "summary": (description or "")[:300],
                "total_cells": total_cells,
                "n_datasets": len(datasets),
                "date": coll.get("published_at", ""),
                "cellxgene_url": f"https://cellxgene.cziscience.com/collections/{coll.get('collection_id', '')}",
            })

        results.sort(key=lambda x: x.get("total_cells", 0), reverse=True)
        return results[:max_results]
    except Exception as e:
        logger.error("CellxGene search failed: %s", e)
        return []


async def search_datasets(
    keywords: list[str],
    organism: str = "Homo sapiens",
    data_type: str = "scRNA-seq",
    min_samples: int = 3,
    sources: list[str] | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    """Search multiple data sources for datasets matching a research plan.

    Queries GEO, TCGA, and CellxGene Census in parallel and returns a
    merged, deduplicated result list sorted by relevance (sample count).
    """
    if sources is None:
        sources = ["geo", "tcga", "cellxgene"]

    tasks = []
    source_names = []

    if "geo" in sources:
        tasks.append(_search_geo(keywords, organism, data_type, min_samples, max_results))
        source_names.append("GEO")
    if "tcga" in sources:
        tasks.append(_search_tcga(keywords, organism, data_type, min_samples, max_results))
        source_names.append("TCGA")
    if "cellxgene" in sources:
        tasks.append(_search_cellxgene(keywords, organism, data_type, min_samples, max_results))
        source_names.append("CellxGene")

    if not tasks:
        return {"success": False, "error": f"No valid sources specified. Choose from: geo, tcga, cellxgene"}

    results_by_source = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: list[dict[str, Any]] = []
    errors: list[str] = []
    for name, res in zip(source_names, results_by_source):
        if isinstance(res, Exception):
            errors.append(f"{name}: {res}")
        elif isinstance(res, list):
            all_results.extend(res)

    all_results.sort(key=lambda x: x.get("sample_count", 0), reverse=True)
    all_results = all_results[:max_results]

    result: dict[str, Any] = {
        "success": True,
        "query": {
            "keywords": keywords,
            "organism": organism,
            "data_type": data_type,
            "min_samples": min_samples,
            "sources": sources,
        },
        "total_found": len(all_results),
        "datasets": all_results,
    }

    if errors:
        result["source_errors"] = errors

    if not all_results:
        result["suggestion"] = (
            "No datasets found. Try: "
            "1) broadening keywords, "
            "2) lowering min_samples, "
            "3) adding more sources, "
            "4) checking organism spelling."
        )

    logger.info(
        "Dataset search complete: %d results from %s",
        len(all_results), ", ".join(source_names),
    )
    return result
