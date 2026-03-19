"""CellxGene Census query tool — search and download from CellxGene Census.

Supports two modes:
1. **Metadata-only** (default): queries the CellxGene REST API for collections
   matching filters — lightweight, no special dependencies.
2. **Data download**: uses ``cellxgene-census`` / ``tiledbsoma`` to pull actual
   expression data into AnnData — requires optional heavy dependencies.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.config import get_config
from bioopenclaw.mcp_servers.data_agent.tools.lineage import LineageTimer, record_step

logger = logging.getLogger(__name__)

CELLXGENE_API = "https://api.cellxgene.cziscience.com/curation/v1"


async def query_cellxgene(
    organism: str = "Homo sapiens",
    tissue: list[str] | None = None,
    disease: list[str] | None = None,
    cell_type: list[str] | None = None,
    assay: str | None = None,
    max_results: int = 20,
    download: bool = False,
    max_cells: int = 100_000,
    output_dir: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Query CellxGene Census for datasets matching biological criteria.

    With ``download=False`` (default), returns metadata only via REST API.
    With ``download=True``, uses ``cellxgene-census`` to pull expression data.
    """
    if download:
        return await _download_from_census(
            organism=organism,
            tissue=tissue,
            disease=disease,
            cell_type=cell_type,
            assay=assay,
            max_cells=max_cells,
            output_dir=output_dir,
            project=project,
        )

    return await _search_collections(
        organism=organism,
        tissue=tissue,
        disease=disease,
        cell_type=cell_type,
        assay=assay,
        max_results=max_results,
    )


async def _search_collections(
    organism: str,
    tissue: list[str] | None,
    disease: list[str] | None,
    cell_type: list[str] | None,
    assay: str | None,
    max_results: int,
) -> dict[str, Any]:
    """Search CellxGene collections via REST API (no heavy deps needed)."""
    try:
        import requests
    except ImportError:
        return {"success": False, "error": "requests not installed"}

    with LineageTimer() as timer:
        try:
            response = requests.get(f"{CELLXGENE_API}/collections", timeout=30)
            response.raise_for_status()
            collections = response.json()
        except Exception as e:
            return {"success": False, "error": f"CellxGene API request failed: {e}"}

        search_terms = []
        if tissue:
            search_terms.extend(t.lower() for t in tissue)
        if disease:
            search_terms.extend(d.lower() for d in disease)
        if cell_type:
            search_terms.extend(c.lower() for c in cell_type)

        matched = []
        for coll in collections:
            title = coll.get("name", "")
            desc = coll.get("description", "")
            combined = f"{title} {desc}".lower()

            if search_terms and not any(term in combined for term in search_terms):
                continue

            datasets = coll.get("datasets", [])

            # Filter by organism
            if organism:
                organism_match = False
                for ds in datasets:
                    for org in ds.get("organism", []):
                        if organism.lower() in org.get("label", "").lower():
                            organism_match = True
                            break
                    if organism_match:
                        break
                if not organism_match and datasets:
                    continue

            # Filter by assay if specified
            if assay:
                assay_match = False
                for ds in datasets:
                    for a in ds.get("assay", []):
                        if assay.lower() in a.get("label", "").lower():
                            assay_match = True
                            break
                    if assay_match:
                        break
                if not assay_match and datasets:
                    continue

            total_cells = sum(d.get("cell_count", 0) for d in datasets)
            tissues_found = set()
            diseases_found = set()
            assays_found = set()
            for ds in datasets:
                for t in ds.get("tissue", []):
                    tissues_found.add(t.get("label", ""))
                for d in ds.get("disease", []):
                    diseases_found.add(d.get("label", ""))
                for a in ds.get("assay", []):
                    assays_found.add(a.get("label", ""))

            matched.append({
                "collection_id": coll.get("collection_id", ""),
                "title": title,
                "description": (desc or "")[:300],
                "n_datasets": len(datasets),
                "total_cells": total_cells,
                "tissues": sorted(tissues_found)[:10],
                "diseases": sorted(diseases_found)[:10],
                "assays": sorted(assays_found)[:5],
                "published_at": coll.get("published_at", ""),
                "url": f"https://cellxgene.cziscience.com/collections/{coll.get('collection_id', '')}",
            })

        matched.sort(key=lambda x: x.get("total_cells", 0), reverse=True)
        matched = matched[:max_results]

    return {
        "success": True,
        "query": {
            "organism": organism,
            "tissue": tissue,
            "disease": disease,
            "cell_type": cell_type,
            "assay": assay,
        },
        "total_found": len(matched),
        "collections": matched,
        "duration_seconds": round(timer.elapsed, 2),
        "note": (
            "These are collection-level results. "
            "To download actual expression data, re-call with download=True."
        ),
    }


async def _download_from_census(
    organism: str,
    tissue: list[str] | None,
    disease: list[str] | None,
    cell_type: list[str] | None,
    assay: str | None,
    max_cells: int,
    output_dir: str | None,
    project: str | None,
) -> dict[str, Any]:
    """Download expression data from CellxGene Census via tiledbsoma."""
    try:
        import cellxgene_census
    except ImportError:
        return {
            "success": False,
            "error": (
                "cellxgene-census not installed. "
                "Install with: pip install cellxgene-census\n"
                "Alternatively, use download=False for metadata-only search."
            ),
        }

    cfg = get_config()
    if output_dir is None:
        output_dir = str(Path(cfg.raw_data_dir) / "cellxgene")
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    obs_filters = []
    if tissue:
        tissue_filter = " or ".join(f'tissue == "{t}"' for t in tissue)
        obs_filters.append(f"({tissue_filter})")
    if disease:
        disease_filter = " or ".join(f'disease == "{d}"' for d in disease)
        obs_filters.append(f"({disease_filter})")
    if cell_type:
        ct_filter = " or ".join(f'cell_type == "{c}"' for c in cell_type)
        obs_filters.append(f"({ct_filter})")
    if assay:
        obs_filters.append(f'assay == "{assay}"')

    obs_value_filter = " and ".join(obs_filters) if obs_filters else None

    with LineageTimer() as timer:
        try:
            census = cellxgene_census.open_soma()
            organism_key = "homo_sapiens" if "homo" in organism.lower() else "mus_musculus"

            adata = cellxgene_census.get_anndata(
                census,
                organism=organism_key,
                obs_value_filter=obs_value_filter,
                column_names={
                    "obs": [
                        "cell_type", "tissue", "disease",
                        "assay", "donor_id", "sex",
                    ],
                },
            )
            census.close()

            if adata.n_obs > max_cells:
                import numpy as np
                rng = np.random.default_rng(42)
                idx = rng.choice(adata.n_obs, size=max_cells, replace=False)
                idx.sort()
                adata = adata[idx].copy()

            filter_desc = obs_value_filter or "none"
            safe_name = filter_desc.replace('"', "").replace(" ", "_")[:50]
            out_file = out_path / f"census_{safe_name}.h5ad"
            adata.write_h5ad(out_file)

        except Exception as e:
            return {
                "success": False,
                "error": f"CellxGene Census download failed: {e}",
                "obs_filter": obs_value_filter,
            }

    result: dict[str, Any] = {
        "success": True,
        "output_path": str(out_file.absolute()),
        "n_cells": adata.n_obs,
        "n_genes": adata.n_vars,
        "obs_columns": list(adata.obs.columns),
        "obs_filter_used": obs_value_filter,
        "cell_type_counts": adata.obs["cell_type"].value_counts().head(10).to_dict()
        if "cell_type" in adata.obs.columns else {},
        "tissue_counts": adata.obs["tissue"].value_counts().head(10).to_dict()
        if "tissue" in adata.obs.columns else {},
        "duration_seconds": round(timer.elapsed, 2),
    }

    if project:
        record_step(
            project=project,
            operation="query_cellxgene",
            output_path=str(out_file.absolute()),
            params={
                "organism": organism,
                "obs_filter": obs_value_filter,
                "max_cells": max_cells,
            },
            metrics={"n_cells": adata.n_obs, "n_genes": adata.n_vars},
            duration_seconds=timer.elapsed,
        )

    return result
