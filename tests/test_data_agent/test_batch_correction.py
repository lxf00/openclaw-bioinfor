"""Tests for batch correction tool."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from bioopenclaw.mcp_servers.data_agent.tools.batch_correction import run_batch_correction


@pytest.fixture
def batch_h5ad(tmp_data_dir: Path) -> Path:
    """Create a .h5ad file with two batches, PCA-ready (normalized+log1p)."""
    import anndata as ad
    import scanpy as sc

    rng = np.random.default_rng(42)
    n_cells, n_genes = 300, 200

    counts = rng.poisson(lam=5, size=(n_cells, n_genes)).astype(np.float32)
    batch_labels = np.array(["batch_A"] * 150 + ["batch_B"] * 150)

    adata = ad.AnnData(X=counts)
    adata.obs["batch"] = batch_labels
    adata.obs_names = [f"Cell_{i}" for i in range(n_cells)]
    adata.var_names = [f"Gene_{i}" for i in range(n_genes)]

    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.pca(adata, n_comps=30)

    p = tmp_data_dir / "batch_test.h5ad"
    adata.write_h5ad(p)
    return p


class TestRunBatchCorrection:
    @pytest.mark.asyncio
    async def test_combat_correction(self, batch_h5ad: Path, output_dir: Path) -> None:
        out = output_dir / "combat_output.h5ad"
        result = await run_batch_correction(
            input_path=str(batch_h5ad),
            output_path=str(out),
            batch_key="batch",
            method="combat",
        )

        assert result["success"] is True
        assert result["method"] == "combat"
        assert result["n_batches"] == 2
        assert out.exists()

    @pytest.mark.asyncio
    async def test_invalid_batch_key(self, batch_h5ad: Path, output_dir: Path) -> None:
        out = output_dir / "invalid_batch.h5ad"
        result = await run_batch_correction(
            input_path=str(batch_h5ad),
            output_path=str(out),
            batch_key="nonexistent_column",
            method="combat",
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_method(self, batch_h5ad: Path, output_dir: Path) -> None:
        out = output_dir / "invalid_method.h5ad"
        result = await run_batch_correction(
            input_path=str(batch_h5ad),
            output_path=str(out),
            batch_key="batch",
            method="not_a_real_method",
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_file_not_found(self, output_dir: Path) -> None:
        result = await run_batch_correction(
            input_path="/nonexistent.h5ad",
            output_path=str(output_dir / "out.h5ad"),
            batch_key="batch",
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_lineage_tracking(
        self, batch_h5ad: Path, output_dir: Path, tmp_data_dir: Path,
    ) -> None:
        out = output_dir / "combat_lineage.h5ad"
        result = await run_batch_correction(
            input_path=str(batch_h5ad),
            output_path=str(out),
            batch_key="batch",
            method="combat",
            project="batch_test_proj",
        )

        assert result["success"] is True
        lineage_file = tmp_data_dir / "lineage" / "batch_test_proj.json"
        assert lineage_file.exists()
