"""Enhanced Scanpy QC tool with built-in validation and lineage tracking."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.tools.lineage import LineageTimer, record_step
from bioopenclaw.mcp_servers.data_agent.tools.validators import (
    detect_log_state,
    validate_anndata_integrity,
    validate_file_exists,
    validate_qc_result,
)

logger = logging.getLogger(__name__)


def _detect_mt_prefix(var_names: Any) -> str:
    """Auto-detect mitochondrial gene prefix across species."""
    prefixes = ["MT-", "mt-", "Mt-"]
    for prefix in prefixes:
        if any(str(g).startswith(prefix) for g in var_names):
            return prefix
    return "MT-"


async def run_scanpy_qc(
    input_path: str,
    output_path: str,
    min_genes: int = 200,
    min_cells: int = 3,
    mt_pct_threshold: float = 20.0,
    run_scrublet: bool = False,
    normalize: bool = False,
    find_hvg: bool = False,
    project: str | None = None,
) -> dict[str, Any]:
    """Run Scanpy single-cell QC with validation checkpoints.

    Returns a structured result dict (never raises on data errors).
    """
    try:
        import anndata  # noqa: F401
        import numpy as np
        import scanpy as sc
    except ImportError as e:
        return {"success": False, "error": f"Dependency not installed: {e}"}

    # --- Pre-validation ---
    file_check = validate_file_exists(input_path)
    if not file_check["valid"]:
        return {"success": False, "error": file_check["message"]}

    with LineageTimer() as timer:
        logger.info("Starting QC: %s", input_path)
        adata = sc.read_h5ad(input_path)

        integrity = validate_anndata_integrity(adata)
        if not integrity["valid"]:
            return {"success": False, "error": integrity["message"]}

        log_state = detect_log_state(adata)
        initial_cells = adata.n_obs
        initial_genes = adata.n_vars

        # Auto-detect mitochondrial gene prefix
        mt_prefix = _detect_mt_prefix(adata.var_names)
        adata.var["mt"] = adata.var_names.str.startswith(mt_prefix)
        mt_gene_count = int(adata.var["mt"].sum())

        sc.pp.calculate_qc_metrics(
            adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True,
        )

        # --- Filtering ---
        sc.pp.filter_cells(adata, min_genes=min_genes)
        sc.pp.filter_genes(adata, min_cells=min_cells)
        adata = adata[adata.obs["pct_counts_mt"] < mt_pct_threshold].copy()

        # --- Optional: doublet detection ---
        doublet_info: dict[str, Any] = {}
        if run_scrublet:
            try:
                import scrublet as scr

                scrub = scr.Scrublet(adata.X)
                doublet_scores, predicted_doublets = scrub.scrub_doublets()
                adata.obs["doublet_score"] = doublet_scores
                adata.obs["predicted_doublet"] = predicted_doublets
                n_doublets = int(predicted_doublets.sum())
                adata = adata[~adata.obs["predicted_doublet"]].copy()
                doublet_info = {
                    "scrublet_ran": True,
                    "doublets_detected": n_doublets,
                    "doublet_rate": f"{n_doublets / len(predicted_doublets) * 100:.1f}%",
                }
            except ImportError:
                doublet_info = {"scrublet_ran": False, "reason": "scrublet not installed"}
            except Exception as exc:
                doublet_info = {"scrublet_ran": False, "reason": str(exc)}

        filtered_cells = adata.n_obs
        filtered_genes = adata.n_vars

        # --- Optional: normalize + log1p ---
        normalization_info: dict[str, Any] = {}
        if normalize:
            if log_state.get("is_log_transformed"):
                normalization_info = {
                    "normalized": False,
                    "reason": "Data appears already log-transformed, skipping log1p",
                }
            else:
                sc.pp.normalize_total(adata, target_sum=1e4)
                sc.pp.log1p(adata)
                normalization_info = {"normalized": True, "method": "normalize_total+log1p"}

        # --- Optional: highly variable genes ---
        hvg_info: dict[str, Any] = {}
        if find_hvg:
            sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
            n_hvg = int(adata.var["highly_variable"].sum())
            hvg_info = {"n_highly_variable_genes": n_hvg}

        # --- Post-validation ---
        qc_check = validate_qc_result(filtered_cells, filtered_genes)

        # --- Save ---
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        adata.write_h5ad(output_path)

    # QC statistics
    mt_stats = {}
    if "pct_counts_mt" in adata.obs.columns:
        mt_stats = {
            "mt_pct_median": round(float(adata.obs["pct_counts_mt"].median()), 2),
            "mt_pct_max": round(float(adata.obs["pct_counts_mt"].max()), 2),
        }

    result: dict[str, Any] = {
        "success": True,
        "initial_cells": initial_cells,
        "initial_genes": initial_genes,
        "filtered_cells": filtered_cells,
        "filtered_genes": filtered_genes,
        "removed_cells": initial_cells - filtered_cells,
        "removal_rate": f"{(initial_cells - filtered_cells) / max(initial_cells, 1) * 100:.1f}%",
        "mt_prefix_detected": mt_prefix,
        "mt_gene_count": mt_gene_count,
        "output_path": str(out.absolute()),
        "qc_params": {
            "min_genes": min_genes,
            "min_cells": min_cells,
            "mt_pct_threshold": mt_pct_threshold,
        },
        "log_state": log_state,
        "qc_check": qc_check,
        "duration_seconds": round(timer.elapsed, 2),
        **mt_stats,
    }

    if doublet_info:
        result["doublet_detection"] = doublet_info
    if normalization_info:
        result["normalization"] = normalization_info
    if hvg_info:
        result["hvg"] = hvg_info

    # Lineage
    if project:
        record_step(
            project=project,
            operation="run_scanpy_qc",
            input_path=input_path,
            output_path=output_path,
            params=result["qc_params"],
            metrics={
                "cells_before": initial_cells,
                "cells_after": filtered_cells,
                "genes_before": initial_genes,
                "genes_after": filtered_genes,
            },
            duration_seconds=timer.elapsed,
        )

    if not qc_check["valid"]:
        result["warning"] = qc_check["message"]

    logger.info("QC complete: %d → %d cells", initial_cells, filtered_cells)
    return result
