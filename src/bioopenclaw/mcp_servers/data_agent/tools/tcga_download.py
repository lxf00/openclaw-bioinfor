"""TCGA data download via GDC API with batch download and AnnData conversion."""

from __future__ import annotations

import gzip
import io
import json
import logging
import tarfile
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.config import get_config
from bioopenclaw.mcp_servers.data_agent.tools.lineage import LineageTimer, record_step
from bioopenclaw.mcp_servers.data_agent.tools.validators import validate_checksum

logger = logging.getLogger(__name__)

GDC_FILES_URL = "https://api.gdc.cancer.gov/files"
GDC_DATA_URL = "https://api.gdc.cancer.gov/data"


async def download_tcga_data(
    project: str,
    data_category: str = "Transcriptome Profiling",
    data_type: str = "Gene Expression Quantification",
    workflow_type: str = "STAR - Counts",
    output_dir: str | None = None,
    max_files: int = 50,
    merge_to_anndata: bool = False,
    project_name: str | None = None,
) -> dict[str, Any]:
    """Download TCGA data from GDC and optionally merge into AnnData.

    Uses the GDC REST API to query and download gene expression files
    for a given TCGA project (e.g. "TCGA-BRCA").
    """
    try:
        import requests
    except ImportError:
        return {"success": False, "error": "requests not installed: pip install requests"}

    cfg = get_config()
    if output_dir is None:
        output_dir = str(Path(cfg.raw_data_dir) / project)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    with LineageTimer() as timer:
        # Step 1: Query matching files
        filters = {
            "op": "and",
            "content": [
                {"op": "in", "content": {"field": "cases.project.project_id", "value": [project]}},
                {"op": "in", "content": {"field": "data_category", "value": [data_category]}},
                {"op": "in", "content": {"field": "data_type", "value": [data_type]}},
                {"op": "in", "content": {"field": "analysis.workflow_type", "value": [workflow_type]}},
            ],
        }

        params = {
            "filters": json.dumps(filters),
            "fields": (
                "file_id,file_name,file_size,cases.case_id,"
                "cases.submitter_id,cases.samples.sample_type,"
                "cases.demographic.gender"
            ),
            "size": str(max_files),
            "format": "JSON",
        }

        logger.info("Querying GDC for %s files...", project)
        try:
            response = requests.get(GDC_FILES_URL, params=params, timeout=60)
            response.raise_for_status()
            query_data = response.json()
        except Exception as e:
            return {"success": False, "error": f"GDC query failed: {e}", "project": project}

        hits = query_data.get("data", {}).get("hits", [])
        if not hits:
            return {
                "success": False,
                "error": f"No files found for project={project}, "
                         f"data_type={data_type}, workflow={workflow_type}",
                "project": project,
            }

        file_ids = [h["file_id"] for h in hits]
        file_metadata = []
        for h in hits:
            case = h.get("cases", [{}])[0] if h.get("cases") else {}
            sample = case.get("samples", [{}])[0] if case.get("samples") else {}
            file_metadata.append({
                "file_id": h["file_id"],
                "file_name": h.get("file_name", ""),
                "file_size": h.get("file_size", 0),
                "case_id": case.get("submitter_id", ""),
                "sample_type": sample.get("sample_type", ""),
            })

        # Step 2: Download files via GDC data endpoint
        manifest_path = out_path / "file_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(file_metadata, f, indent=2)

        downloaded_files: list[str] = []
        download_errors: list[str] = []

        for i, fmeta in enumerate(file_metadata):
            fid = fmeta["file_id"]
            fname = fmeta["file_name"]
            target = out_path / fname

            if target.exists():
                downloaded_files.append(fname)
                continue

            logger.info(
                "Downloading %d/%d: %s (%s)",
                i + 1, len(file_metadata), fname,
                _human_size(fmeta.get("file_size", 0)),
            )

            retries = cfg.download_max_retries
            for attempt in range(1, retries + 1):
                try:
                    r = requests.get(
                        f"{GDC_DATA_URL}/{fid}",
                        timeout=cfg.download_timeout_seconds,
                        stream=True,
                    )
                    r.raise_for_status()

                    with open(target, "wb") as out_f:
                        for chunk in r.iter_content(chunk_size=8192):
                            out_f.write(chunk)

                    downloaded_files.append(fname)
                    break
                except Exception as e:
                    if attempt == retries:
                        download_errors.append(f"{fname}: {e}")
                        logger.error("Download failed for %s: %s", fname, e)
                    else:
                        import asyncio
                        await asyncio.sleep(cfg.download_retry_delay_seconds)

    result: dict[str, Any] = {
        "success": True,
        "project": project,
        "query": {
            "data_category": data_category,
            "data_type": data_type,
            "workflow_type": workflow_type,
        },
        "total_files_found": len(hits),
        "files_downloaded": len(downloaded_files),
        "output_dir": str(out_path.absolute()),
        "manifest_path": str(manifest_path.absolute()),
        "sample_metadata": file_metadata[:5],
        "duration_seconds": round(timer.elapsed, 2),
    }

    if download_errors:
        result["download_errors"] = download_errors
        result["warning"] = f"{len(download_errors)} files failed to download"

    # Optionally merge into AnnData
    if merge_to_anndata and downloaded_files:
        merge_result = await _merge_tcga_to_anndata(out_path, downloaded_files, project)
        result["anndata_merge"] = merge_result

    if project_name:
        record_step(
            project=project_name,
            operation="download_tcga_data",
            output_path=str(out_path.absolute()),
            params={
                "tcga_project": project,
                "data_type": data_type,
                "workflow_type": workflow_type,
            },
            metrics={
                "files_found": len(hits),
                "files_downloaded": len(downloaded_files),
            },
            duration_seconds=timer.elapsed,
        )

    logger.info(
        "TCGA download complete: %s, %d/%d files",
        project, len(downloaded_files), len(hits),
    )
    return result


async def _merge_tcga_to_anndata(
    data_dir: Path,
    file_names: list[str],
    project: str,
) -> dict[str, Any]:
    """Attempt to merge TCGA count files into a single AnnData object."""
    try:
        import anndata as ad
        import numpy as np
        import pandas as pd
    except ImportError:
        return {"success": False, "error": "anndata/pandas not installed"}

    count_frames = []
    sample_ids = []

    for fname in file_names:
        fpath = data_dir / fname
        if not fpath.exists():
            continue

        try:
            if fname.endswith(".gz"):
                df = pd.read_csv(fpath, sep="\t", comment="#", compression="gzip")
            elif fname.endswith(".tsv") or fname.endswith(".txt"):
                df = pd.read_csv(fpath, sep="\t", comment="#")
            else:
                continue

            if len(df.columns) >= 2:
                gene_col = df.columns[0]
                count_col = df.columns[-1]
                series = df.set_index(gene_col)[count_col]
                series = series[~series.index.str.startswith("__")]
                count_frames.append(series)
                sample_ids.append(fname.split(".")[0])
        except Exception as e:
            logger.debug("Could not parse %s: %s", fname, e)

    if not count_frames:
        return {"success": False, "error": "No parseable count files found"}

    merged = pd.concat(count_frames, axis=1, join="inner")
    merged.columns = sample_ids

    adata = ad.AnnData(X=merged.T.values.astype(np.float32))
    adata.obs_names = sample_ids
    adata.var_names = list(merged.index)

    out_h5ad = data_dir / f"{project}_merged.h5ad"
    adata.write_h5ad(out_h5ad)

    return {
        "success": True,
        "merged_path": str(out_h5ad),
        "n_samples": adata.n_obs,
        "n_genes": adata.n_vars,
    }


def _human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
