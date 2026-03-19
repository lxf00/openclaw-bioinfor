"""Dataset inspection tool — reports shape, units, log state, batch info."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.tools.validators import (
    detect_data_unit,
    detect_log_state,
    validate_anndata_integrity,
    validate_file_exists,
)

logger = logging.getLogger(__name__)


async def inspect_dataset(file_path: str) -> dict[str, Any]:
    """Inspect a .h5ad file and return a comprehensive summary.

    Returns shape, data unit, log state, batch info, QC metric ranges,
    obs/var columns, and actionable recommendations.
    """
    try:
        import numpy as np
        import scanpy as sc
    except ImportError as e:
        return {"success": False, "error": f"Dependency not installed: {e}"}

    file_check = validate_file_exists(file_path)
    if not file_check["valid"]:
        return {"success": False, "error": file_check["message"]}

    p = Path(file_path)
    if p.suffix not in (".h5ad", ".h5"):
        return {
            "success": False,
            "error": f"Unsupported format: {p.suffix}. Use convert_data_format first.",
        }

    logger.info("Inspecting dataset: %s", file_path)
    adata = sc.read_h5ad(file_path)

    integrity = validate_anndata_integrity(adata)
    if not integrity["valid"]:
        return {"success": False, "error": integrity["message"]}

    log_state = detect_log_state(adata)
    data_unit = detect_data_unit(adata)

    # Mitochondrial gene detection
    mt_info: dict[str, Any] = {}
    for prefix in ["MT-", "mt-", "Mt-"]:
        mt_mask = adata.var_names.str.startswith(prefix)
        if mt_mask.any():
            mt_info["mt_prefix"] = prefix
            mt_info["mt_gene_count"] = int(mt_mask.sum())
            break

    if not mt_info:
        mt_info = {"mt_prefix": "none detected", "mt_gene_count": 0}

    # Batch info
    potential_batch_cols = []
    for col in adata.obs.columns:
        n_unique = adata.obs[col].nunique()
        if 2 <= n_unique <= min(100, adata.n_obs // 10):
            potential_batch_cols.append({"column": col, "n_unique": n_unique})

    # Basic stats
    if hasattr(adata.X, "toarray"):
        x = adata.X.toarray()
    else:
        x = np.asarray(adata.X)

    sparsity = float(1.0 - np.count_nonzero(x) / max(x.size, 1))

    # Gene count distribution per cell
    genes_per_cell = np.array((adata.X > 0).sum(axis=1)).flatten()

    result: dict[str, Any] = {
        "success": True,
        "file_path": str(p.absolute()),
        "file_size_mb": round(p.stat().st_size / 1e6, 2),
        "shape": {"n_cells": adata.n_obs, "n_genes": adata.n_vars},
        "data_unit": data_unit,
        "log_state": log_state,
        "sparsity": f"{sparsity * 100:.1f}%",
        "genes_per_cell": {
            "min": int(genes_per_cell.min()),
            "median": int(np.median(genes_per_cell)),
            "max": int(genes_per_cell.max()),
        },
        "mt_info": mt_info,
        "obs_columns": list(adata.obs.columns),
        "var_columns": list(adata.var.columns),
        "potential_batch_columns": potential_batch_cols,
        "obsm_keys": list(adata.obsm.keys()) if adata.obsm else [],
        "layers": list(adata.layers.keys()) if adata.layers else [],
    }

    # Recommendations
    recommendations: list[str] = []
    if log_state.get("is_log_transformed"):
        recommendations.append("Data appears log-transformed. Do NOT apply log1p again.")
    if data_unit.get("unit") == "TPM":
        recommendations.append("Data is in TPM. Suitable for visualization but re-normalize from counts for DE analysis.")
    if not potential_batch_cols:
        recommendations.append("No obvious batch columns detected. Batch correction may not be needed.")
    if mt_info.get("mt_gene_count", 0) == 0:
        recommendations.append("No mitochondrial genes detected. QC mt% filtering will have no effect.")
    result["recommendations"] = recommendations

    logger.info(
        "Inspection complete: %d cells × %d genes, unit=%s",
        adata.n_obs, adata.n_vars, data_unit.get("unit", "unknown"),
    )
    return result
