"""Tests for lineage tracking module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bioopenclaw.mcp_servers.data_agent.tools.lineage import (
    LineageTimer,
    get_lineage,
    record_step,
)


class TestRecordStep:
    def test_creates_lineage_file(self, tmp_data_dir: Path) -> None:
        record_step(
            project="test_project",
            operation="download_geo_data",
            output_path="data/raw/GSE123456/",
            params={"gse_id": "GSE123456"},
        )

        lineage_file = tmp_data_dir / "lineage" / "test_project.json"
        assert lineage_file.exists()

        data = json.loads(lineage_file.read_text(encoding="utf-8"))
        assert data["project"] == "test_project"
        assert len(data["lineage"]) == 1
        assert data["lineage"][0]["step"] == 1
        assert data["lineage"][0]["operation"] == "download_geo_data"

    def test_appends_steps(self, tmp_data_dir: Path) -> None:
        record_step(project="multi_step", operation="step_1")
        record_step(project="multi_step", operation="step_2")
        record_step(project="multi_step", operation="step_3")

        data = get_lineage("multi_step")
        assert len(data["lineage"]) == 3
        assert data["lineage"][0]["step"] == 1
        assert data["lineage"][2]["step"] == 3

    def test_records_metrics(self, tmp_data_dir: Path) -> None:
        record_step(
            project="metrics_test",
            operation="run_scanpy_qc",
            metrics={"cells_before": 10000, "cells_after": 8500},
        )

        data = get_lineage("metrics_test")
        assert data["lineage"][0]["metrics"]["cells_before"] == 10000

    def test_records_checksum(self, tmp_data_dir: Path) -> None:
        record_step(
            project="checksum_test",
            operation="download",
            checksum="sha256:abc123",
        )

        data = get_lineage("checksum_test")
        assert data["lineage"][0]["checksum"] == "sha256:abc123"


class TestGetLineage:
    def test_empty_project(self, tmp_data_dir: Path) -> None:
        data = get_lineage("nonexistent_project")
        assert data["project"] == "nonexistent_project"
        assert data["lineage"] == []


class TestLineageTimer:
    def test_measures_elapsed(self) -> None:
        import time

        with LineageTimer() as timer:
            time.sleep(0.05)

        assert timer.elapsed >= 0.04
        assert timer.elapsed < 1.0
