"""Batch correction tool — Harmony, Combat, and scVI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.tools.lineage import LineageTimer, record_step
from bioopenclaw.mcp_servers.data_agent.tools.validators import (
    validate_batch_key,
    validate_file_exists,
)

logger = logging.getLogger(__name__)

SUPPORTED_METHODS = ("harmony", "combat", "scvi")


async def run_batch_correction(
    input_path: str,
    output_path: str,
    batch_key: str,
    method: str = "harmony",
    n_pcs: int = 30,
    project: str | None = None,
) -> dict[str, Any]:
    """Run batch correction on an AnnData object.

    Methods:
    - ``harmony``: Harmony integration (modifies obsm, fast)
    - ``combat``: ComBat correction (modifies X, for DE analysis)
    - ``scvi``: scVI integration (modifies obsm, deep learning)
    """
    try:
        import numpy as np
        import scanpy as sc
    except ImportError as e:
        return {"success": False, "error": f"Dependency not installed: {e}"}

    if method not in SUPPORTED_METHODS:
        return {
            "success": False,
            "error": f"Unknown method '{method}'. Supported: {SUPPORTED_METHODS}",
        }

    file_check = validate_file_exists(input_path)
    if not file_check["valid"]:
        return {"success": False, "error": file_check["message"]}

    with LineageTimer() as timer:
        adata = sc.read_h5ad(input_path)

        # Pre-validation: batch key
        batch_check = validate_batch_key(adata, batch_key)
        if not batch_check["valid"]:
            return {"success": False, "error": batch_check["message"]}

        n_batches = batch_check["n_batches"]
        logger.info(
            "Batch correction: method=%s, batch_key=%s, n_batches=%d",
            method, batch_key, n_batches,
        )

        # Ensure PCA is computed
        if "X_pca" not in adata.obsm:
            logger.info("Computing PCA (n_pcs=%d)...", n_pcs)
            sc.pp.pca(adata, n_comps=n_pcs)

        # Run batch correction
        if method == "harmony":
            correction_result = await _run_harmony(adata, batch_key)
        elif method == "combat":
            correction_result = await _run_combat(adata, batch_key)
        elif method == "scvi":
            correction_result = await _run_scvi(adata, batch_key)
        else:
            return {"success": False, "error": f"Method '{method}' not implemented"}

        if not correction_result.get("success"):
            return correction_result

        # Recompute neighbors + UMAP on corrected embedding
        rep_key = correction_result.get("representation_key", "X_pca")
        sc.pp.neighbors(adata, use_rep=rep_key)
        sc.tl.umap(adata)

        # Save
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        adata.write_h5ad(output_path)

    result: dict[str, Any] = {
        "success": True,
        "method": method,
        "batch_key": batch_key,
        "n_batches": n_batches,
        "batch_values": batch_check.get("batch_values", []),
        "representation_key": rep_key,
        "n_cells": adata.n_obs,
        "n_genes": adata.n_vars,
        "output_path": str(out.absolute()),
        "duration_seconds": round(timer.elapsed, 2),
        **{k: v for k, v in correction_result.items() if k not in ("success", "representation_key")},
    }

    if project:
        record_step(
            project=project,
            operation="run_batch_correction",
            input_path=input_path,
            output_path=output_path,
            params={
                "method": method,
                "batch_key": batch_key,
                "n_pcs": n_pcs,
                "n_batches": n_batches,
            },
            duration_seconds=timer.elapsed,
        )

    logger.info("Batch correction complete: %s (%d batches)", method, n_batches)
    return result


async def _run_harmony(adata: Any, batch_key: str) -> dict[str, Any]:
    """Run Harmony on PCA embedding."""
    try:
        import harmonypy
    except ImportError:
        try:
            from harmony import harmonize
            harmony_data = harmonize(adata.obsm["X_pca"], adata.obs, batch_key)
            adata.obsm["X_pca_harmony"] = harmony_data
            return {"success": True, "representation_key": "X_pca_harmony"}
        except ImportError:
            return {
                "success": False,
                "error": "Neither harmonypy nor harmony-pytorch installed. "
                         "Install with: pip install harmonypy",
            }

    ho = harmonypy.run_harmony(
        adata.obsm["X_pca"],
        adata.obs,
        batch_key,
    )
    adata.obsm["X_pca_harmony"] = ho.Z_corr.T

    return {
        "success": True,
        "representation_key": "X_pca_harmony",
        "harmony_converged": bool(ho.converged) if hasattr(ho, "converged") else True,
    }


async def _run_combat(adata: Any, batch_key: str) -> dict[str, Any]:
    """Run ComBat on the expression matrix (modifies X directly)."""
    try:
        import scanpy as sc
        sc.pp.combat(adata, key=batch_key)
    except Exception as e:
        return {"success": False, "error": f"ComBat failed: {e}"}

    return {
        "success": True,
        "representation_key": "X_pca",
        "note": "ComBat modifies the expression matrix (X) directly. Suitable for DE analysis.",
    }


async def _run_scvi(adata: Any, batch_key: str) -> dict[str, Any]:
    """Run scVI for deep generative batch correction."""
    try:
        import scvi
    except ImportError:
        return {
            "success": False,
            "error": "scvi-tools not installed. Install with: pip install scvi-tools",
        }

    try:
        scvi.model.SCVI.setup_anndata(adata, batch_key=batch_key)
        model = scvi.model.SCVI(adata)
        model.train(max_epochs=100, early_stopping=True, progress_bar_threshold=0)
        adata.obsm["X_scVI"] = model.get_latent_representation()
    except Exception as e:
        return {"success": False, "error": f"scVI training failed: {e}"}

    return {
        "success": True,
        "representation_key": "X_scVI",
        "note": "scVI learned a latent representation. Use X_scVI for downstream clustering.",
    }
