"""RCSB PDB protein structure query tool.

Uses the RCSB PDB Search API v2 and Data API to search for protein
structures and optionally download PDB/mmCIF files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.config import get_config
from bioopenclaw.mcp_servers.data_agent.tools.lineage import LineageTimer, record_step

logger = logging.getLogger(__name__)

PDB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
PDB_DATA_URL = "https://data.rcsb.org/rest/v1/core/entry"
PDB_DOWNLOAD_URL = "https://files.rcsb.org/download"


async def query_pdb(
    query: str,
    organism: str | None = None,
    method: str | None = None,
    resolution_max: float | None = None,
    max_results: int = 10,
    download_structure: bool = False,
    file_format: str = "pdb",
    output_dir: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Search RCSB PDB for protein structures.

    Parameters
    ----------
    query : str
        Search term — protein name, gene name, or UniProt accession.
    organism : str, optional
        Filter by organism scientific name.
    method : str, optional
        Experimental method filter (e.g. "X-RAY DIFFRACTION", "ELECTRON MICROSCOPY").
    resolution_max : float, optional
        Maximum resolution in Angstroms (e.g. 2.5).
    max_results : int
        Maximum number of results.
    download_structure : bool
        If True, download structure files for all results.
    file_format : str
        Download format: "pdb" or "cif" (mmCIF).
    output_dir : str, optional
        Directory for downloaded files.
    project : str, optional
        Project name for lineage tracking.
    """
    try:
        import requests
    except ImportError:
        return {"success": False, "error": "requests not installed"}

    with LineageTimer() as timer:
        search_query = _build_search_query(query, organism, method, resolution_max)

        logger.info("PDB search: %s", query)

        try:
            response = requests.post(
                PDB_SEARCH_URL,
                json=search_query,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            return {"success": False, "error": f"PDB Search API failed: {e}"}

        result_set = data.get("result_set", [])
        pdb_ids = [r.get("identifier", "") for r in result_set[:max_results]]

        if not pdb_ids:
            return {
                "success": True,
                "query": query,
                "total_found": 0,
                "entries": [],
                "suggestion": "No structures found. Try broader search terms or remove filters.",
            }

        entries = await _fetch_entry_details(pdb_ids)

        download_info: dict[str, Any] = {}
        if download_structure and pdb_ids:
            download_info = await _download_structures(pdb_ids, file_format, output_dir)

    result: dict[str, Any] = {
        "success": True,
        "query": query,
        "total_found": len(entries),
        "entries": entries,
        "duration_seconds": round(timer.elapsed, 2),
    }

    if download_info:
        result["structure_download"] = download_info

    if project:
        record_step(
            project=project,
            operation="query_pdb",
            params={"query": query, "max_results": max_results},
            metrics={"total_found": len(entries)},
            duration_seconds=timer.elapsed,
        )

    logger.info("PDB search complete: %d structures for '%s'", len(entries), query)
    return result


def _build_search_query(
    query: str,
    organism: str | None,
    method: str | None,
    resolution_max: float | None,
) -> dict[str, Any]:
    """Build an RCSB PDB Search API v2 query."""
    nodes: list[dict[str, Any]] = [
        {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": query},
        }
    ]

    if organism:
        nodes.append({
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_entity_source_organism.ncbi_scientific_name",
                "operator": "exact_match",
                "value": organism,
            },
        })

    if method:
        nodes.append({
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "exptl.method",
                "operator": "exact_match",
                "value": method,
            },
        })

    if resolution_max is not None:
        nodes.append({
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_entry_info.resolution_combined",
                "operator": "less_or_equal",
                "value": resolution_max,
            },
        })

    if len(nodes) == 1:
        query_node = nodes[0]
    else:
        query_node = {
            "type": "group",
            "logical_operator": "and",
            "nodes": nodes,
        }

    return {
        "query": query_node,
        "return_type": "entry",
        "request_options": {"results_content_type": ["experimental"]},
    }


async def _fetch_entry_details(pdb_ids: list[str]) -> list[dict[str, Any]]:
    """Fetch summary details for a list of PDB IDs."""
    import requests

    entries: list[dict[str, Any]] = []
    for pdb_id in pdb_ids:
        try:
            r = requests.get(f"{PDB_DATA_URL}/{pdb_id}", timeout=15)
            r.raise_for_status()
            d = r.json()

            resolution = None
            if d.get("rcsb_entry_info", {}).get("resolution_combined"):
                res_list = d["rcsb_entry_info"]["resolution_combined"]
                resolution = res_list[0] if res_list else None

            entries.append({
                "pdb_id": pdb_id,
                "title": d.get("struct", {}).get("title", ""),
                "method": d.get("exptl", [{}])[0].get("method", "") if d.get("exptl") else "",
                "resolution": resolution,
                "deposit_date": d.get("rcsb_accession_info", {}).get("deposit_date", ""),
                "polymer_count": d.get("rcsb_entry_info", {}).get("polymer_entity_count", 0),
                "pdb_url": f"https://www.rcsb.org/structure/{pdb_id}",
            })
        except Exception as e:
            logger.debug("Could not fetch details for %s: %s", pdb_id, e)
            entries.append({"pdb_id": pdb_id, "error": str(e)})

    return entries


async def _download_structures(
    pdb_ids: list[str],
    file_format: str,
    output_dir: str | None,
) -> dict[str, Any]:
    """Download PDB/mmCIF structure files."""
    import requests

    cfg = get_config()
    if output_dir is None:
        output_dir = str(Path(cfg.raw_data_dir) / "pdb")
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ext = "pdb" if file_format == "pdb" else "cif"
    downloaded: list[str] = []
    errors: list[str] = []

    for pdb_id in pdb_ids:
        fname = f"{pdb_id}.{ext}"
        target = out_path / fname

        if target.exists():
            downloaded.append(fname)
            continue

        try:
            url = f"{PDB_DOWNLOAD_URL}/{pdb_id}.{ext}"
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            target.write_bytes(r.content)
            downloaded.append(fname)
        except Exception as e:
            errors.append(f"{pdb_id}: {e}")

    return {
        "downloaded": len(downloaded),
        "output_dir": str(out_path.absolute()),
        "files": downloaded,
        "format": file_format,
        "errors": errors if errors else None,
    }
