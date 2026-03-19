"""Tests for GEO download tool (mock-based, no network)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bioopenclaw.mcp_servers.data_agent.tools.geo_download import download_geo_data


class TestDownloadGeoData:
    @pytest.mark.asyncio
    async def test_missing_email_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATA_AGENT_ENTREZ_EMAIL", "")
        from bioopenclaw.mcp_servers.data_agent import config
        config._config = None

        result = await download_geo_data(gse_id="GSE123456", email="")
        assert result["success"] is False
        assert "email" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_successful_download_mock(
        self, output_dir: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_gse = MagicMock()
        mock_gse.gsms = {"GSM001": None, "GSM002": None, "GSM003": None}
        mock_gse.gpls = {"GPL570": None}
        mock_gse.metadata = {
            "title": ["Test Dataset"],
            "sample_organism_ch1": ["Homo sapiens"],
            "summary": ["Raw counts from single cell RNA-seq experiment"],
        }

        with patch("GEOparse.get_GEO", return_value=mock_gse):
            result = await download_geo_data(
                gse_id="GSE123456",
                output_dir=str(output_dir / "geo_test"),
            )

        assert result["success"] is True
        assert result["gse_id"] == "GSE123456"
        assert result["gsm_count"] == 3
        assert result["organism"] == "Homo sapiens"

    @pytest.mark.asyncio
    async def test_download_failure_retries(
        self, output_dir: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("DATA_AGENT_DOWNLOAD_MAX_RETRIES", "1")
        monkeypatch.setenv("DATA_AGENT_DOWNLOAD_RETRY_DELAY_SECONDS", "0")
        from bioopenclaw.mcp_servers.data_agent import config
        config._config = None

        with patch("GEOparse.get_GEO", side_effect=ConnectionError("timeout")):
            result = await download_geo_data(
                gse_id="GSE999999",
                output_dir=str(output_dir / "geo_fail"),
            )

        assert result["success"] is False
        assert "failed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_lineage_recorded_on_success(
        self, output_dir: Path, tmp_data_dir: Path,
    ) -> None:
        mock_gse = MagicMock()
        mock_gse.gsms = {"GSM001": None}
        mock_gse.gpls = {"GPL570": None}
        mock_gse.metadata = {
            "title": ["Test"],
            "sample_organism_ch1": ["Homo sapiens"],
            "summary": ["counts"],
        }

        with patch("GEOparse.get_GEO", return_value=mock_gse):
            result = await download_geo_data(
                gse_id="GSE111111",
                output_dir=str(output_dir / "geo_lineage"),
                project="lineage_test",
            )

        assert result["success"] is True
        lineage_file = tmp_data_dir / "lineage" / "lineage_test.json"
        assert lineage_file.exists()
