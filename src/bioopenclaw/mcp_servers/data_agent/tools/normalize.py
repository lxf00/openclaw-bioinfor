"""Data normalization tool with log-state detection to prevent double-log1p."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.tools.lineage import LineageTimer, record_step
from bioopenclaw.mcp_servers.data_agent.tools.validators import (
    detect_log_state,
    validate_anndata_integrity,
    validate_file_exists,
)

logger = logging.getLogger(__name__)


async def normalize_data(
    input_path: str,
    output_path: str,
    method: str = "scanpy_default",
    target_sum: float = 1e4,
    check_log_state: bool = True,
    project: str | None = None,
) -> dict[str, Any]:
    """Normalize an AnnData object.

    Methods:
    - ``scanpy_default``: normalize_total + log1p (standard Scanpy workflow)
    - ``log1p_only``: log1p only (data already library-size normalized)
    - ``total_only``: normalize_total only (no log transform)

    If *check_log_state* is True (default), the tool auto-detects whether
    data is already log-transformed and skips log1p to prevent double-logging.
    """
    try:
        import numpy as np
        import scanpy as sc
    except ImportError as e:
        return {"success": False, "error": f"Dependency not installed: {e}"}

    file_check = validate_file_exists(input_path)
    if not file_check["valid"]:
        return {"success": False, "error": file_check["message"]}

    valid_methods = ("scanpy_default", "log1p_only", "total_only")
    if method not in valid_methods:
        return {"success": False, "error": f"Unknown method '{method}'. Choose from {valid_methods}"}

    with LineageTimer() as timer:
        adata = sc.read_h5ad(input_path)

        integrity = validate_anndata_integrity(adata)
        if not integrity["valid"]:
            return {"success": False, "error": integrity["message"]}

        # Pre-validation: detect log state
        log_check = detect_log_state(adata)
        already_logged = log_check.get("is_log_transformed", False)
        skipped_log = False

        if check_log_state and already_logged and method in ("scanpy_default", "log1p_only"):
            skipped_log = True
            logger.warning(
                "Data appears already log-transformed (max=%.2f). Skipping log1p.",
                log_check.get("max_value", 0),
            )

        # Apply normalization
        applied_steps: list[str] = []

        if method == "scanpy_default":
            sc.pp.normalize_total(adata, target_sum=target_sum)
            applied_steps.append(f"normalize_total(target_sum={target_sum})")
            if not skipped_log:
                sc.pp.log1p(adata)
                applied_steps.append("log1p")

        elif method == "log1p_only":
            if not skipped_log:
                sc.pp.log1p(adata)
                applied_steps.append("log1p")

        elif method == "total_only":
            sc.pp.normalize_total(adata, target_sum=target_sum)
            applied_steps.append(f"normalize_total(target_sum={target_sum})")

        # Post-validation: check value range
        if hasattr(adata.X, "toarray"):
            x_max = float(adata.X.toarray().max())
            x_min = float(adata.X.toarray().min())
        else:
            x_max = float(np.max(adata.X))
            x_min = float(np.min(adata.X))

        # Save
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        adata.write_h5ad(output_path)

    result: dict[str, Any] = {
        "success": True,
        "method": method,
        "applied_steps": applied_steps,
        "skipped_log1p": skipped_log,
        "pre_log_state": log_check,
        "post_value_range": {"min": round(x_min, 4), "max": round(x_max, 4)},
        "output_path": str(out.absolute()),
        "n_cells": adata.n_obs,
        "n_genes": adata.n_vars,
        "duration_seconds": round(timer.elapsed, 2),
    }

    if skipped_log:
        result["warning"] = (
            "log1p was SKIPPED because data appears already log-transformed. "
            "If this is incorrect, re-run with check_log_state=False."
        )

    if project:
        record_step(
            project=project,
            operation="normalize_data",
            input_path=input_path,
            output_path=output_path,
            params={"method": method, "target_sum": target_sum, "skipped_log": skipped_log},
            duration_seconds=timer.elapsed,
        )

    logger.info("Normalization complete: %s, steps=%s", method, applied_steps)
    return result
