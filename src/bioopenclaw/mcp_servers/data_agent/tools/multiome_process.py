"""Multi-omics data processing tool using Muon (MuData).

Supports CITE-seq (RNA + ADT/protein), Multiome (RNA + ATAC),
and Spatial Transcriptomics data. Each modality gets independent
QC, with optional weighted nearest neighbors (WNN) integration.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.tools.lineage import LineageTimer, record_step

logger = logging.getLogger(__name__)

SUPPORTED_MODALITIES = ("rna", "adt", "atac", "spatial")


async def process_multiome(
    input_paths: dict[str, str],
    output_path: str,
    modalities: list[str] | None = None,
    qc_rna: dict[str, Any] | None = None,
    qc_protein: dict[str, Any] | None = None,
    run_integration: bool = False,
    project: str | None = None,
) -> dict[str, Any]:
    """Process multi-modal single-cell data.

    Parameters
    ----------
    input_paths : dict[str, str]
        Mapping of modality name to file path, e.g.
        ``{"rna": "rna.h5ad", "adt": "adt.h5ad"}`` or
        ``{"mudata": "combined.h5mu"}``.
    output_path : str
        Output file path (.h5mu for MuData or .h5ad for single modality).
    modalities : list[str], optional
        Which modalities to process. Defaults to all found in input.
    qc_rna : dict, optional
        RNA QC parameters: ``{"min_genes": 200, "min_cells": 3, "mt_pct": 20}``.
    qc_protein : dict, optional
        ADT/protein QC parameters: ``{"min_counts": 100}``.
    run_integration : bool
        If True, run multi-modal integration (WNN or basic concatenation).
    project : str, optional
        Project name for lineage tracking.
    """
    try:
        import muon as mu
    except ImportError:
        return {
            "success": False,
            "error": (
                "muon not installed. Install with: pip install muon\n"
                "For full multi-omics support: pip install 'bioopenclaw[multiomics]'"
            ),
        }

    try:
        import anndata as ad
        import numpy as np
        import scanpy as sc
    except ImportError as e:
        return {"success": False, "error": f"Dependency not installed: {e}"}

    with LineageTimer() as timer:
        # Load data
        if "mudata" in input_paths:
            try:
                mdata = mu.read(input_paths["mudata"])
            except Exception as e:
                return {"success": False, "error": f"Failed to read MuData: {e}"}
        else:
            adata_dict: dict[str, Any] = {}
            for mod_name, mod_path in input_paths.items():
                if mod_name in SUPPORTED_MODALITIES:
                    try:
                        adata_dict[mod_name] = sc.read_h5ad(mod_path)
                    except Exception as e:
                        return {
                            "success": False,
                            "error": f"Failed to read {mod_name} from {mod_path}: {e}",
                        }

            if not adata_dict:
                return {
                    "success": False,
                    "error": f"No valid modalities found. Provide keys from: {SUPPORTED_MODALITIES}",
                }

            try:
                mdata = mu.MuData(adata_dict)
            except Exception as e:
                return {"success": False, "error": f"Failed to create MuData: {e}"}

        available_mods = list(mdata.mod.keys())
        target_mods = modalities or available_mods
        unknown_mods = [m for m in target_mods if m not in available_mods]
        if unknown_mods:
            return {
                "success": False,
                "error": f"Modalities {unknown_mods} not in data. Available: {available_mods}",
            }

        mod_summaries: dict[str, dict[str, Any]] = {}

        # QC per modality
        for mod_name in target_mods:
            adata_mod = mdata.mod[mod_name]
            initial_cells = adata_mod.n_obs
            initial_genes = adata_mod.n_vars

            if mod_name == "rna":
                params = qc_rna or {}
                min_genes = params.get("min_genes", 200)
                min_cells = params.get("min_cells", 3)
                mt_pct = params.get("mt_pct", 20.0)

                for prefix in ["MT-", "mt-", "Mt-"]:
                    if any(str(g).startswith(prefix) for g in adata_mod.var_names):
                        adata_mod.var["mt"] = adata_mod.var_names.str.startswith(prefix)
                        break
                else:
                    adata_mod.var["mt"] = False

                sc.pp.calculate_qc_metrics(
                    adata_mod, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True,
                )
                sc.pp.filter_cells(adata_mod, min_genes=min_genes)
                sc.pp.filter_genes(adata_mod, min_cells=min_cells)
                if "pct_counts_mt" in adata_mod.obs.columns:
                    adata_mod._inplace_subset_obs(
                        adata_mod.obs["pct_counts_mt"] < mt_pct
                    )

                mod_summaries["rna"] = {
                    "initial_cells": initial_cells,
                    "filtered_cells": adata_mod.n_obs,
                    "initial_genes": initial_genes,
                    "filtered_genes": adata_mod.n_vars,
                    "qc_params": {"min_genes": min_genes, "min_cells": min_cells, "mt_pct": mt_pct},
                }

            elif mod_name == "adt":
                params = qc_protein or {}
                min_counts = params.get("min_counts", 100)

                sc.pp.calculate_qc_metrics(adata_mod, percent_top=None, log1p=False, inplace=True)
                if "total_counts" in adata_mod.obs.columns:
                    adata_mod._inplace_subset_obs(
                        adata_mod.obs["total_counts"] >= min_counts
                    )

                mod_summaries["adt"] = {
                    "initial_cells": initial_cells,
                    "filtered_cells": adata_mod.n_obs,
                    "n_proteins": adata_mod.n_vars,
                    "qc_params": {"min_counts": min_counts},
                }

            elif mod_name == "atac":
                sc.pp.calculate_qc_metrics(adata_mod, percent_top=None, log1p=False, inplace=True)
                mod_summaries["atac"] = {
                    "initial_cells": initial_cells,
                    "filtered_cells": adata_mod.n_obs,
                    "n_peaks": adata_mod.n_vars,
                }

            else:
                mod_summaries[mod_name] = {
                    "cells": adata_mod.n_obs,
                    "features": adata_mod.n_vars,
                }

        # Intersect cells across modalities
        mu.pp.intersect_obs(mdata)
        mdata.update()

        # Optional integration
        integration_info: dict[str, Any] = {}
        if run_integration and len(target_mods) > 1:
            try:
                if "rna" in mdata.mod:
                    rna = mdata.mod["rna"]
                    sc.pp.normalize_total(rna, target_sum=1e4)
                    sc.pp.log1p(rna)
                    sc.pp.pca(rna)

                if "adt" in mdata.mod:
                    adt = mdata.mod["adt"]
                    mu.prot.pp.clr(adt)
                    sc.pp.pca(adt)

                mu.pp.neighbors(mdata)
                mu.tl.umap(mdata)

                integration_info = {
                    "method": "muon_neighbors",
                    "total_cells": mdata.n_obs,
                }
            except Exception as e:
                integration_info = {"method": "failed", "error": str(e)}

        # Save
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        mdata.write(output_path)

    result: dict[str, Any] = {
        "success": True,
        "modalities": available_mods,
        "processed_modalities": target_mods,
        "total_cells_after_intersect": mdata.n_obs,
        "modality_summaries": mod_summaries,
        "output_path": str(out.absolute()),
        "output_format": "h5mu",
        "duration_seconds": round(timer.elapsed, 2),
    }

    if integration_info:
        result["integration"] = integration_info

    if project:
        record_step(
            project=project,
            operation="process_multiome",
            input_path=str(input_paths),
            output_path=output_path,
            params={"modalities": target_mods, "run_integration": run_integration},
            metrics={
                "total_cells": mdata.n_obs,
                "modalities": available_mods,
            },
            duration_seconds=timer.elapsed,
        )

    logger.info(
        "Multiome processing complete: %s, %d cells",
        ", ".join(available_mods), mdata.n_obs,
    )
    return result
