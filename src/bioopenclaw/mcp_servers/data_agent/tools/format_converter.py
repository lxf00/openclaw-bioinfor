"""Data format converter — converts various bioinformatics formats to .h5ad."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.tools.lineage import LineageTimer, record_step
from bioopenclaw.mcp_servers.data_agent.tools.validators import (
    validate_anndata_integrity,
    validate_file_exists,
)

logger = logging.getLogger(__name__)

SUPPORTED_INPUT_FORMATS = ("10x_mtx", "csv", "tsv", "loom", "h5", "h5ad")


async def convert_data_format(
    input_path: str,
    output_path: str,
    input_format: str,
    gene_column: str | None = None,
    delimiter: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Convert bioinformatics data to AnnData .h5ad format.

    Supported input formats:
    - ``10x_mtx``: 10x Genomics Market Exchange format (directory with matrix.mtx, genes.tsv, barcodes.tsv)
    - ``csv`` / ``tsv``: Delimited text (genes x cells or cells x genes)
    - ``loom``: Loom format
    - ``h5``: 10x Genomics HDF5 format
    - ``h5ad``: AnnData format (copy/re-save)
    """
    try:
        import anndata as ad
        import scanpy as sc
    except ImportError as e:
        return {"success": False, "error": f"Dependency not installed: {e}"}

    if input_format not in SUPPORTED_INPUT_FORMATS:
        return {
            "success": False,
            "error": f"Unsupported format '{input_format}'. Supported: {SUPPORTED_INPUT_FORMATS}",
        }

    file_check = validate_file_exists(input_path)
    if not file_check["valid"] and input_format != "10x_mtx":
        return {"success": False, "error": file_check["message"]}

    if input_format == "10x_mtx" and not Path(input_path).is_dir():
        return {
            "success": False,
            "error": f"For 10x_mtx format, input_path must be a directory: {input_path}",
        }

    with LineageTimer() as timer:
        logger.info("Converting %s (%s) → h5ad", input_path, input_format)

        try:
            if input_format == "10x_mtx":
                adata = sc.read_10x_mtx(input_path, var_names="gene_symbols", cache=False)

            elif input_format in ("csv", "tsv"):
                sep = delimiter or ("," if input_format == "csv" else "\t")
                adata = ad.read_csv(input_path, delimiter=sep)
                if gene_column and gene_column in adata.obs.columns:
                    adata = adata.T

            elif input_format == "loom":
                adata = sc.read_loom(input_path)

            elif input_format == "h5":
                adata = sc.read_10x_h5(input_path)

            elif input_format == "h5ad":
                adata = sc.read_h5ad(input_path)

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read {input_format} file: {e}",
                "input_path": input_path,
            }

        integrity = validate_anndata_integrity(adata)
        if not integrity["valid"]:
            return {"success": False, "error": f"Converted data invalid: {integrity['message']}"}

        adata.var_names_make_unique()

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        adata.write_h5ad(output_path)

    result: dict[str, Any] = {
        "success": True,
        "input_format": input_format,
        "input_path": input_path,
        "output_path": str(out.absolute()),
        "n_cells": adata.n_obs,
        "n_genes": adata.n_vars,
        "obs_columns": list(adata.obs.columns),
        "var_columns": list(adata.var.columns),
        "duration_seconds": round(timer.elapsed, 2),
    }

    if project:
        record_step(
            project=project,
            operation="convert_data_format",
            input_path=input_path,
            output_path=output_path,
            params={"input_format": input_format},
            metrics={"n_cells": adata.n_obs, "n_genes": adata.n_vars},
            duration_seconds=timer.elapsed,
        )

    logger.info(
        "Conversion complete: %s → h5ad (%d cells × %d genes)",
        input_format, adata.n_obs, adata.n_vars,
    )
    return result
