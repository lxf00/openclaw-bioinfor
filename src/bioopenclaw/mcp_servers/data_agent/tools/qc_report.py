"""QC report generator — creates Markdown reports from AnnData files."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.config import get_config
from bioopenclaw.mcp_servers.data_agent.tools.lineage import LineageTimer, record_step
from bioopenclaw.mcp_servers.data_agent.tools.validators import (
    detect_data_unit,
    detect_log_state,
    validate_file_exists,
)

logger = logging.getLogger(__name__)


async def generate_qc_report(
    input_path: str,
    output_path: str | None = None,
    report_path: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Generate a Markdown QC report from AnnData file(s).

    If *output_path* is provided (post-QC file), generates a before/after comparison.
    If only *input_path* is provided, generates a single-dataset summary.
    """
    try:
        import numpy as np
        import scanpy as sc
    except ImportError as e:
        return {"success": False, "error": f"Dependency not installed: {e}"}

    file_check = validate_file_exists(input_path)
    if not file_check["valid"]:
        return {"success": False, "error": file_check["message"]}

    cfg = get_config()
    if report_path is None:
        name = Path(input_path).stem
        report_path = str(Path(cfg.reports_dir) / f"{name}_qc_report.md")

    with LineageTimer() as timer:
        adata_pre = sc.read_h5ad(input_path)
        adata_post = None

        if output_path:
            post_check = validate_file_exists(output_path)
            if post_check["valid"]:
                adata_post = sc.read_h5ad(output_path)

        report_lines = _build_report(
            adata_pre=adata_pre,
            adata_post=adata_post,
            input_path=input_path,
            output_path=output_path,
        )

        report_text = "\n".join(report_lines)
        rp = Path(report_path)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(report_text, encoding="utf-8")

    result: dict[str, Any] = {
        "success": True,
        "report_path": str(rp.absolute()),
        "report_length_lines": len(report_lines),
        "summary": {
            "pre_cells": adata_pre.n_obs,
            "pre_genes": adata_pre.n_vars,
        },
        "duration_seconds": round(timer.elapsed, 2),
    }

    if adata_post is not None:
        result["summary"]["post_cells"] = adata_post.n_obs
        result["summary"]["post_genes"] = adata_post.n_vars
        result["summary"]["cells_removed"] = adata_pre.n_obs - adata_post.n_obs
        result["summary"]["removal_rate"] = (
            f"{(adata_pre.n_obs - adata_post.n_obs) / max(adata_pre.n_obs, 1) * 100:.1f}%"
        )

    if project:
        record_step(
            project=project,
            operation="generate_qc_report",
            input_path=input_path,
            output_path=report_path,
            params={"post_qc_path": output_path},
            duration_seconds=timer.elapsed,
        )

    logger.info("QC report generated: %s", report_path)
    return result


def _build_report(
    adata_pre: Any,
    adata_post: Any | None,
    input_path: str,
    output_path: str | None,
) -> list[str]:
    """Build the Markdown report content."""
    import numpy as np

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# QC Report",
        "",
        f"**Generated**: {now}",
        f"**Input file**: `{input_path}`",
    ]
    if output_path:
        lines.append(f"**Post-QC file**: `{output_path}`")
    lines.append("")

    # --- Pre-QC summary ---
    lines.extend([
        "## Pre-QC Dataset Summary",
        "",
        f"- **Cells**: {adata_pre.n_obs:,}",
        f"- **Genes**: {adata_pre.n_vars:,}",
        f"- **File size**: {Path(input_path).stat().st_size / 1e6:.1f} MB",
    ])

    log_state = detect_log_state(adata_pre)
    data_unit = detect_data_unit(adata_pre)
    lines.extend([
        f"- **Data unit**: {data_unit.get('unit', 'unknown')}",
        f"- **Log-transformed**: {'Yes' if log_state.get('is_log_transformed') else 'No'} "
        f"(max value: {log_state.get('max_value', 'N/A')})",
    ])

    # MT genes
    for prefix in ["MT-", "mt-", "Mt-"]:
        mt_mask = adata_pre.var_names.str.startswith(prefix)
        if mt_mask.any():
            lines.append(f"- **Mitochondrial genes**: {int(mt_mask.sum())} ({prefix}*)")
            break

    # obs columns
    lines.extend([
        "",
        f"**Observation columns**: {', '.join(adata_pre.obs.columns[:15])}",
    ])

    # --- QC metrics (if available) ---
    if "pct_counts_mt" in adata_pre.obs.columns:
        mt_pct = adata_pre.obs["pct_counts_mt"]
        lines.extend([
            "",
            "## QC Metrics Distribution (Pre-QC)",
            "",
            "| Metric | Min | Median | Mean | Max |",
            "|--------|-----|--------|------|-----|",
            f"| MT% | {mt_pct.min():.1f} | {mt_pct.median():.1f} | {mt_pct.mean():.1f} | {mt_pct.max():.1f} |",
        ])
        if "n_genes_by_counts" in adata_pre.obs.columns:
            ngenes = adata_pre.obs["n_genes_by_counts"]
            lines.append(
                f"| Genes/cell | {ngenes.min():.0f} | {ngenes.median():.0f} | {ngenes.mean():.0f} | {ngenes.max():.0f} |"
            )
        if "total_counts" in adata_pre.obs.columns:
            tcounts = adata_pre.obs["total_counts"]
            lines.append(
                f"| Total counts | {tcounts.min():.0f} | {tcounts.median():.0f} | {tcounts.mean():.0f} | {tcounts.max():.0f} |"
            )

    # --- Post-QC comparison ---
    if adata_post is not None:
        removed_cells = adata_pre.n_obs - adata_post.n_obs
        removed_genes = adata_pre.n_vars - adata_post.n_vars
        lines.extend([
            "",
            "## Post-QC Comparison",
            "",
            "| | Pre-QC | Post-QC | Removed |",
            "|---|--------|---------|---------|",
            f"| Cells | {adata_pre.n_obs:,} | {adata_post.n_obs:,} | {removed_cells:,} ({removed_cells / max(adata_pre.n_obs, 1) * 100:.1f}%) |",
            f"| Genes | {adata_pre.n_vars:,} | {adata_post.n_vars:,} | {removed_genes:,} |",
        ])

        if "pct_counts_mt" in adata_post.obs.columns:
            mt_post = adata_post.obs["pct_counts_mt"]
            lines.extend([
                "",
                f"**Post-QC MT%**: median={mt_post.median():.1f}%, max={mt_post.max():.1f}%",
            ])

    # --- Batch info ---
    potential_batch = []
    target = adata_post if adata_post is not None else adata_pre
    for col in target.obs.columns:
        n_unique = target.obs[col].nunique()
        if 2 <= n_unique <= min(50, target.n_obs // 10):
            potential_batch.append(f"{col} ({n_unique} values)")

    if potential_batch:
        lines.extend([
            "",
            "## Potential Batch Columns",
            "",
        ])
        for pb in potential_batch:
            lines.append(f"- {pb}")

    # --- Recommendations ---
    lines.extend([
        "",
        "## Recommendations",
        "",
    ])
    recommendations = []
    if log_state.get("is_log_transformed"):
        recommendations.append("Data is log-transformed. Skip log1p in normalization.")
    if adata_post and adata_post.n_obs < 500:
        recommendations.append("WARNING: Very few cells remain after QC. Consider relaxing thresholds.")
    if potential_batch:
        recommendations.append(
            f"Batch columns detected ({len(potential_batch)}). "
            "Consider running batch correction if samples come from different batches."
        )
    if not potential_batch:
        recommendations.append("No obvious batch columns. Batch correction likely not needed.")

    if not recommendations:
        recommendations.append("Dataset looks good for downstream analysis.")

    for rec in recommendations:
        lines.append(f"- {rec}")

    lines.append("")
    return lines
