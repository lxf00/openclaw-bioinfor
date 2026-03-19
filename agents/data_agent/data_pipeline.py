"""Data Agent high-level pipeline interface for direct invocation.

This module provides a convenience wrapper around the MCP tools so that
pipelines can be launched programmatically (e.g. from a script or notebook)
without going through the MCP protocol.

Usage::

    import asyncio
    from agents.data_agent.data_pipeline import DataPipeline

    async def main():
        dp = DataPipeline(project="BRCA1_scRNA")

        # Download
        await dp.download_geo("GSE123456")

        # QC
        await dp.run_qc(min_genes=200, mt_pct_threshold=20.0)

        # Report
        await dp.generate_report()

    asyncio.run(main())
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DataPipeline:
    """High-level pipeline controller for Data Agent tasks."""

    def __init__(
        self,
        project: str,
        data_dir: str = "./data",
    ) -> None:
        self.project = project
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw" / project
        self.processed_dir = self.data_dir / "processed" / project
        self.reports_dir = self.data_dir / "reports"

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self._last_output: str | None = None
        self._step_count = 0

    @property
    def last_output(self) -> str | None:
        return self._last_output

    async def download_geo(self, gse_id: str, **kwargs: Any) -> dict[str, Any]:
        from bioopenclaw.mcp_servers.data_agent.tools.geo_download import download_geo_data

        result = await download_geo_data(
            gse_id=gse_id,
            output_dir=str(self.raw_dir),
            project=self.project,
            **kwargs,
        )
        if result.get("success"):
            self._last_output = result.get("output_dir")
        return result

    async def download_tcga(self, tcga_project: str, **kwargs: Any) -> dict[str, Any]:
        from bioopenclaw.mcp_servers.data_agent.tools.tcga_download import download_tcga_data

        result = await download_tcga_data(
            project=tcga_project,
            output_dir=str(self.raw_dir),
            project_name=self.project,
            **kwargs,
        )
        if result.get("success"):
            self._last_output = result.get("output_dir")
        return result

    async def inspect(self, file_path: str | None = None) -> dict[str, Any]:
        from bioopenclaw.mcp_servers.data_agent.tools.data_inspector import inspect_dataset

        path = file_path or self._last_output
        if not path:
            return {"success": False, "error": "No file to inspect. Download or specify file_path."}
        return await inspect_dataset(file_path=path)

    async def run_qc(
        self,
        input_path: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from bioopenclaw.mcp_servers.data_agent.tools.scanpy_qc import run_scanpy_qc

        inp = input_path or self._last_output
        if not inp:
            return {"success": False, "error": "No input file. Download data first."}

        self._step_count += 1
        out = str(self.processed_dir / f"step{self._step_count}_qc.h5ad")

        result = await run_scanpy_qc(
            input_path=inp,
            output_path=out,
            project=self.project,
            **kwargs,
        )
        if result.get("success"):
            self._last_output = result.get("output_path", out)
        return result

    async def normalize(
        self,
        input_path: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from bioopenclaw.mcp_servers.data_agent.tools.normalize import normalize_data

        inp = input_path or self._last_output
        if not inp:
            return {"success": False, "error": "No input file."}

        self._step_count += 1
        out = str(self.processed_dir / f"step{self._step_count}_normalized.h5ad")

        result = await normalize_data(
            input_path=inp,
            output_path=out,
            project=self.project,
            **kwargs,
        )
        if result.get("success"):
            self._last_output = result.get("output_path", out)
        return result

    async def batch_correct(
        self,
        batch_key: str,
        input_path: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from bioopenclaw.mcp_servers.data_agent.tools.batch_correction import run_batch_correction

        inp = input_path or self._last_output
        if not inp:
            return {"success": False, "error": "No input file."}

        self._step_count += 1
        out = str(self.processed_dir / f"step{self._step_count}_batch_corrected.h5ad")

        result = await run_batch_correction(
            input_path=inp,
            output_path=out,
            batch_key=batch_key,
            project=self.project,
            **kwargs,
        )
        if result.get("success"):
            self._last_output = result.get("output_path", out)
        return result

    async def generate_report(
        self,
        pre_qc_path: str | None = None,
        post_qc_path: str | None = None,
    ) -> dict[str, Any]:
        from bioopenclaw.mcp_servers.data_agent.tools.qc_report import generate_qc_report

        inp = pre_qc_path or self._last_output
        if not inp:
            return {"success": False, "error": "No input file."}

        report = str(self.reports_dir / f"{self.project}_qc_report.md")

        return await generate_qc_report(
            input_path=inp,
            output_path=post_qc_path,
            report_path=report,
            project=self.project,
        )

    async def run_full_pipeline(self, config: dict[str, Any]) -> dict[str, Any]:
        """Run a full pipeline via the pipeline orchestration tool."""
        from bioopenclaw.mcp_servers.data_agent.tools.pipeline import run_pipeline

        config.setdefault("project", self.project)
        config.setdefault("output_dir", str(self.processed_dir))
        return await run_pipeline(pipeline_config=config)
