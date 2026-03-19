"""Tests for QC report generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioopenclaw.mcp_servers.data_agent.tools.qc_report import generate_qc_report
from bioopenclaw.mcp_servers.data_agent.tools.scanpy_qc import run_scanpy_qc


class TestGenerateQcReport:
    @pytest.mark.asyncio
    async def test_single_file_report(self, small_h5ad: Path, output_dir: Path) -> None:
        report = output_dir / "test_report.md"
        result = await generate_qc_report(
            input_path=str(small_h5ad),
            report_path=str(report),
        )

        assert result["success"] is True
        assert report.exists()
        content = report.read_text(encoding="utf-8")
        assert "# QC Report" in content
        assert "Pre-QC Dataset Summary" in content

    @pytest.mark.asyncio
    async def test_before_after_comparison(
        self, small_h5ad: Path, output_dir: Path,
    ) -> None:
        qc_out = output_dir / "qc_for_report.h5ad"
        await run_scanpy_qc(
            input_path=str(small_h5ad),
            output_path=str(qc_out),
            min_genes=5,
            min_cells=1,
            mt_pct_threshold=50.0,
        )

        report = output_dir / "comparison_report.md"
        result = await generate_qc_report(
            input_path=str(small_h5ad),
            output_path=str(qc_out),
            report_path=str(report),
        )

        assert result["success"] is True
        assert "post_cells" in result["summary"]
        content = report.read_text(encoding="utf-8")
        assert "Post-QC Comparison" in content

    @pytest.mark.asyncio
    async def test_file_not_found(self, output_dir: Path) -> None:
        result = await generate_qc_report(
            input_path="/nonexistent.h5ad",
            report_path=str(output_dir / "fail_report.md"),
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_default_report_path(self, small_h5ad: Path) -> None:
        result = await generate_qc_report(input_path=str(small_h5ad))

        assert result["success"] is True
        assert result["report_path"].endswith("_qc_report.md")

    @pytest.mark.asyncio
    async def test_report_contains_recommendations(
        self, small_h5ad: Path, output_dir: Path,
    ) -> None:
        report = output_dir / "rec_report.md"
        result = await generate_qc_report(
            input_path=str(small_h5ad),
            report_path=str(report),
        )

        assert result["success"] is True
        content = report.read_text(encoding="utf-8")
        assert "Recommendations" in content
