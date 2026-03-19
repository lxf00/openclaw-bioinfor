"""Data validation checkpoints used by all tools.

Every public function returns a ``ValidationResult`` dict so that tools can
embed pre-/post-validation without raising exceptions.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

ValidationResult = dict[str, Any]


def ok(message: str = "passed", **extra: Any) -> ValidationResult:
    return {"valid": True, "message": message, **extra}


def fail(message: str, **extra: Any) -> ValidationResult:
    return {"valid": False, "message": message, **extra}


# ---------------------------------------------------------------------------
# File-level validators
# ---------------------------------------------------------------------------

def validate_file_exists(path: str) -> ValidationResult:
    """Check that a file exists and is not empty."""
    p = Path(path)
    if not p.exists():
        return fail(f"File not found: {path}")
    if p.stat().st_size == 0:
        return fail(f"File is empty: {path}")
    return ok("file exists", size_bytes=p.stat().st_size)


def validate_checksum(path: str, expected: str | None = None, algorithm: str = "sha256") -> ValidationResult:
    """Compute file checksum; optionally verify against *expected*."""
    p = Path(path)
    if not p.exists():
        return fail(f"File not found: {path}")

    h = hashlib.new(algorithm)
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    computed = h.hexdigest()

    if expected and computed != expected:
        return fail(
            f"Checksum mismatch ({algorithm}): expected {expected}, got {computed}",
            computed=computed,
        )
    return ok(f"{algorithm} checksum computed", checksum=f"{algorithm}:{computed}")


# ---------------------------------------------------------------------------
# AnnData-level validators
# ---------------------------------------------------------------------------

def detect_log_state(adata: Any) -> ValidationResult:
    """Heuristic: if max(X) < 30 the data is likely log-transformed.

    Raw counts typically have max values in the thousands; log1p(counts)
    usually stays below ~15.  We use 30 as a conservative threshold.
    """
    try:
        if hasattr(adata.X, "toarray"):
            x_max = float(adata.X.toarray().max())
        else:
            x_max = float(np.max(adata.X))
    except Exception as exc:
        return fail(f"Cannot read expression matrix: {exc}")

    is_log = x_max < 30
    return ok(
        "log state detected",
        is_log_transformed=is_log,
        max_value=x_max,
        hint="Data appears log-transformed" if is_log else "Data appears to be raw counts",
    )


def detect_data_unit(adata: Any) -> ValidationResult:
    """Best-effort detection of FPKM / TPM / raw counts.

    Heuristic based on value distribution:
    - Raw counts: integers, max >> 100
    - TPM / FPKM: floats, row sums near 1e6 (TPM) or variable (FPKM)
    - log-transformed: max < 30
    """
    try:
        if hasattr(adata.X, "toarray"):
            x = adata.X.toarray()
        else:
            x = np.asarray(adata.X)
    except Exception as exc:
        return fail(f"Cannot read expression matrix: {exc}")

    x_max = float(x.max())
    x_min = float(x.min())

    if x_max < 30:
        unit = "log-transformed (unknown base unit)"
    elif np.allclose(x, x.astype(int)):
        unit = "counts"
    else:
        row_sums = x.sum(axis=1)
        median_sum = float(np.median(row_sums))
        if 0.8e6 < median_sum < 1.2e6:
            unit = "TPM"
        else:
            unit = "FPKM_or_normalized"

    return ok(
        "data unit detected",
        unit=unit,
        max_value=x_max,
        min_value=x_min,
    )


def validate_batch_key(adata: Any, batch_key: str) -> ValidationResult:
    """Check that *batch_key* exists in ``adata.obs`` and has >= 2 unique values."""
    if batch_key not in adata.obs.columns:
        return fail(
            f"batch_key '{batch_key}' not found in adata.obs. "
            f"Available columns: {list(adata.obs.columns)}"
        )
    n_batches = adata.obs[batch_key].nunique()
    if n_batches < 2:
        return fail(
            f"batch_key '{batch_key}' has only {n_batches} unique value(s); "
            "batch correction requires >= 2 batches"
        )
    return ok(
        "batch key valid",
        batch_key=batch_key,
        n_batches=n_batches,
        batch_values=list(adata.obs[batch_key].unique()[:10]),
    )


def validate_anndata_integrity(adata: Any) -> ValidationResult:
    """Basic sanity checks on an AnnData object."""
    issues: list[str] = []

    if adata.n_obs == 0:
        issues.append("AnnData has 0 observations (cells)")
    if adata.n_vars == 0:
        issues.append("AnnData has 0 variables (genes)")
    if adata.X is None:
        issues.append("Expression matrix (X) is None")

    if issues:
        return fail("; ".join(issues))

    return ok(
        "AnnData integrity OK",
        n_obs=adata.n_obs,
        n_vars=adata.n_vars,
        obs_columns=list(adata.obs.columns),
        var_columns=list(adata.var.columns),
    )


def validate_qc_result(
    cells_after: int,
    genes_after: int,
    min_cells: int = 500,
    min_genes: int = 2000,
) -> ValidationResult:
    """Post-QC stop condition: abort if too few cells or genes remain."""
    issues: list[str] = []
    if cells_after < min_cells:
        issues.append(f"Only {cells_after} cells remain (threshold: {min_cells})")
    if genes_after < min_genes:
        issues.append(f"Only {genes_after} genes remain (threshold: {min_genes})")

    if issues:
        return fail(
            "QC result below threshold — recommend stopping and reviewing parameters. " +
            "; ".join(issues),
            cells_after=cells_after,
            genes_after=genes_after,
        )
    return ok("QC result within acceptable range", cells_after=cells_after, genes_after=genes_after)
