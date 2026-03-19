"""UniProt protein database query tool.

Uses the UniProt REST API (https://rest.uniprot.org/) to search for
proteins by gene name, protein name, or keyword, and optionally
download FASTA sequences.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.config import get_config
from bioopenclaw.mcp_servers.data_agent.tools.lineage import LineageTimer, record_step

logger = logging.getLogger(__name__)

UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_ENTRY_URL = "https://rest.uniprot.org/uniprotkb"


async def query_uniprot(
    query: str,
    organism: str | None = None,
    reviewed_only: bool = True,
    max_results: int = 10,
    fields: list[str] | None = None,
    download_fasta: bool = False,
    output_dir: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Search UniProt for proteins matching a query.

    Parameters
    ----------
    query : str
        Search term — gene name (e.g. "BRCA1"), protein name, or keyword.
    organism : str, optional
        Filter by organism (e.g. "Homo sapiens", "9606").
    reviewed_only : bool
        If True, search only Swiss-Prot (reviewed) entries.
    max_results : int
        Maximum number of results to return.
    fields : list[str], optional
        Specific fields to retrieve. Defaults to a standard set.
    download_fasta : bool
        If True, download FASTA sequences for all results.
    output_dir : str, optional
        Directory to save FASTA files (defaults to data/raw/uniprot/).
    project : str, optional
        Project name for lineage tracking.
    """
    try:
        import requests
    except ImportError:
        return {"success": False, "error": "requests not installed"}

    with LineageTimer() as timer:
        query_parts = [query]
        if organism:
            if organism.isdigit():
                query_parts.append(f"(organism_id:{organism})")
            else:
                query_parts.append(f'(organism_name:"{organism}")')
        if reviewed_only:
            query_parts.append("(reviewed:true)")

        full_query = " AND ".join(query_parts)

        if fields is None:
            fields = [
                "accession", "id", "protein_name", "gene_names",
                "organism_name", "length", "go_p", "sequence",
            ]

        params = {
            "query": full_query,
            "format": "json",
            "size": max_results,
            "fields": ",".join(fields),
        }

        logger.info("UniProt search: %s", full_query)

        try:
            response = requests.get(UNIPROT_SEARCH_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            return {"success": False, "error": f"UniProt API request failed: {e}"}

        results_raw = data.get("results", [])
        entries: list[dict[str, Any]] = []

        for entry in results_raw:
            protein_name = ""
            rec_name = entry.get("proteinDescription", {}).get("recommendedName")
            if rec_name:
                protein_name = rec_name.get("fullName", {}).get("value", "")

            gene_names = []
            for g in entry.get("genes", []):
                if g.get("geneName"):
                    gene_names.append(g["geneName"].get("value", ""))

            entries.append({
                "accession": entry.get("primaryAccession", ""),
                "entry_name": entry.get("uniProtkbId", ""),
                "protein_name": protein_name,
                "gene_names": gene_names,
                "organism": entry.get("organism", {}).get("scientificName", ""),
                "length": entry.get("sequence", {}).get("length", 0),
                "uniprot_url": f"https://www.uniprot.org/uniprot/{entry.get('primaryAccession', '')}",
            })

        fasta_info: dict[str, Any] = {}
        if download_fasta and entries:
            fasta_info = await _download_fastas(entries, output_dir)

    result: dict[str, Any] = {
        "success": True,
        "query": full_query,
        "total_found": len(entries),
        "entries": entries,
        "duration_seconds": round(timer.elapsed, 2),
    }

    if fasta_info:
        result["fasta_download"] = fasta_info

    if project:
        record_step(
            project=project,
            operation="query_uniprot",
            params={"query": full_query, "max_results": max_results},
            metrics={"total_found": len(entries)},
            duration_seconds=timer.elapsed,
        )

    logger.info("UniProt search complete: %d results for '%s'", len(entries), query)
    return result


async def _download_fastas(
    entries: list[dict[str, Any]],
    output_dir: str | None,
) -> dict[str, Any]:
    """Download FASTA sequences for the given UniProt entries."""
    import requests

    cfg = get_config()
    if output_dir is None:
        output_dir = str(Path(cfg.raw_data_dir) / "uniprot")
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    downloaded: list[str] = []
    errors: list[str] = []

    for entry in entries:
        acc = entry["accession"]
        fasta_path = out_path / f"{acc}.fasta"

        if fasta_path.exists():
            downloaded.append(acc)
            continue

        try:
            url = f"{UNIPROT_ENTRY_URL}/{acc}.fasta"
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            fasta_path.write_text(r.text, encoding="utf-8")
            downloaded.append(acc)
        except Exception as e:
            errors.append(f"{acc}: {e}")

    return {
        "downloaded": len(downloaded),
        "output_dir": str(out_path.absolute()),
        "files": [f"{acc}.fasta" for acc in downloaded],
        "errors": errors if errors else None,
    }
