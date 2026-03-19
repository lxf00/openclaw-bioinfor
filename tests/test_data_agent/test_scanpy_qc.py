"""Tests for the enhanced Scanpy QC tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioopenclaw.mcp_servers.data_agent.tools.scanpy_qc import run_scanpy_qc


class TestRunScanpyQC:
    @pytest.mark.asyncio
    async def test_basic_qc(self, small_h5ad: Path, output_dir: Path) -> None:
        out = output_dir / "qc_output.h5ad"
        result = await run_scanpy_qc(
            input_path=str(small_h5ad),
            output_path=str(out),
            min_genes=5,
            min_cells=1,
            mt_pct_threshold=50.0,
        )

        assert result["success"] is True
        assert result["initial_cells"] == 200
        assert result["filtered_cells"] <= 200
        assert result["mt_prefix_detected"] == "MT-"
        assert out.exists()

    @pytest.mark.asyncio
    async def test_file_not_found(self, output_dir: Path) -> None:
        result = await run_scanpy_qc(
            input_path="/nonexistent.h5ad",
            output_path=str(output_dir / "out.h5ad"),
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_qc_with_project_tracking(
        self, small_h5ad: Path, output_dir: Path, tmp_data_dir: Path,
    ) -> None:
        out = output_dir / "qc_tracked.h5ad"
        result = await run_scanpy_qc(
            input_path=str(small_h5ad),
            output_path=str(out),
            min_genes=5,
            min_cells=1,
            mt_pct_threshold=50.0,
            project="test_qc_lineage",
        )

        assert result["success"] is True
        lineage_file = tmp_data_dir / "lineage" / "test_qc_lineage.json"
        assert lineage_file.exists()

    @pytest.mark.asyncio
    async def test_qc_returns_log_state(self, small_h5ad: Path, output_dir: Path) -> None:
        out = output_dir / "qc_logstate.h5ad"
        result = await run_scanpy_qc(
            input_path=str(small_h5ad),
            output_path=str(out),
            min_genes=5,
            min_cells=1,
        )
        assert "log_state" in result

    @pytest.mark.asyncio
    async def test_normalize_skips_if_logged(
        self, logged_h5ad: Path, output_dir: Path,
    ) -> None:
        out = output_dir / "qc_norm_logged.h5ad"
        result = await run_scanpy_qc(
            input_path=str(logged_h5ad),
            output_path=str(out),
            min_genes=1,
            min_cells=1,
            mt_pct_threshold=100.0,
            normalize=True,
        )
        assert result["success"] is True
        if "normalization" in result:
            assert result["normalization"].get("normalized") is False
