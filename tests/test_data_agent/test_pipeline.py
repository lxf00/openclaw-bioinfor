"""Tests for pipeline orchestration tool."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from bioopenclaw.mcp_servers.data_agent.tools.pipeline import run_pipeline


class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_qc_only_pipeline(self, small_h5ad: Path, output_dir: Path) -> None:
        config = {
            "name": "test_qc_pipeline",
            "project": "test_pipe",
            "steps": [
                {
                    "tool": "run_scanpy_qc",
                    "params": {
                        "input_path": str(small_h5ad),
                        "min_genes": 5,
                        "min_cells": 1,
                        "mt_pct_threshold": 50.0,
                    },
                },
            ],
            "output_dir": str(output_dir / "pipeline_out"),
        }

        result = await run_pipeline(pipeline_config=config)

        assert result["success"] is True
        assert result["completed_steps"] == 1
        assert result["final_output_path"] is not None

    @pytest.mark.asyncio
    async def test_multi_step_pipeline(self, small_h5ad: Path, output_dir: Path) -> None:
        config = {
            "name": "test_multi_step",
            "project": "test_multi",
            "steps": [
                {
                    "tool": "run_scanpy_qc",
                    "params": {
                        "input_path": str(small_h5ad),
                        "min_genes": 5,
                        "min_cells": 1,
                        "mt_pct_threshold": 50.0,
                    },
                },
                {
                    "tool": "inspect_dataset",
                    "params": {},
                },
            ],
            "output_dir": str(output_dir / "multi_out"),
        }

        result = await run_pipeline(pipeline_config=config)

        assert result["success"] is True
        assert result["completed_steps"] == 2
        assert len(result["steps"]) == 2

    @pytest.mark.asyncio
    async def test_empty_pipeline_fails(self) -> None:
        result = await run_pipeline(pipeline_config={"name": "empty", "steps": []})

        assert result["success"] is False
        assert "no steps" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_unknown_tool_fails(self) -> None:
        config = {
            "name": "bad_tool",
            "steps": [{"tool": "nonexistent_tool", "params": {}}],
        }

        result = await run_pipeline(pipeline_config=config)
        assert result["success"] is False
        assert "unknown" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_pipeline_stops_on_failure(self, output_dir: Path) -> None:
        config = {
            "name": "fail_test",
            "project": "fail_proj",
            "steps": [
                {
                    "tool": "run_scanpy_qc",
                    "params": {
                        "input_path": "/nonexistent.h5ad",
                    },
                },
                {
                    "tool": "inspect_dataset",
                    "params": {},
                },
            ],
            "output_dir": str(output_dir / "fail_out"),
        }

        result = await run_pipeline(pipeline_config=config)

        assert result["success"] is False
        assert result["completed_steps"] == 1
        assert result["steps"][0]["success"] is False

    @pytest.mark.asyncio
    async def test_pipeline_writes_experiment_record(
        self, small_h5ad: Path, output_dir: Path,
    ) -> None:
        config = {
            "name": "experiment_record_test",
            "project": "exp_rec_test",
            "steps": [
                {
                    "tool": "run_scanpy_qc",
                    "params": {
                        "input_path": str(small_h5ad),
                        "min_genes": 5,
                        "min_cells": 1,
                        "mt_pct_threshold": 50.0,
                    },
                },
            ],
            "output_dir": str(output_dir / "exp_out"),
        }

        result = await run_pipeline(pipeline_config=config)
        assert result["success"] is True

        experiments = list(Path("shared_memory/experiments").glob("*experiment_record_test*"))
        assert len(experiments) >= 1
        content = experiments[0].read_text(encoding="utf-8")
        assert "experiment_record_test" in content

    @pytest.mark.asyncio
    async def test_lineage_recorded(
        self, small_h5ad: Path, output_dir: Path, tmp_data_dir: Path,
    ) -> None:
        config = {
            "name": "lineage_pipe",
            "project": "lineage_pipe_test",
            "steps": [
                {
                    "tool": "run_scanpy_qc",
                    "params": {
                        "input_path": str(small_h5ad),
                        "min_genes": 5,
                        "min_cells": 1,
                        "mt_pct_threshold": 50.0,
                    },
                },
            ],
            "output_dir": str(output_dir / "lineage_out"),
        }

        await run_pipeline(pipeline_config=config)

        lineage_file = tmp_data_dir / "lineage" / "lineage_pipe_test.json"
        assert lineage_file.exists()
