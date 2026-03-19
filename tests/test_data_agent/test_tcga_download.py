"""Tests for TCGA download tool (mock-based)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bioopenclaw.mcp_servers.data_agent.tools.tcga_download import download_tcga_data


class TestDownloadTcgaData:
    @pytest.mark.asyncio
    async def test_successful_query_mock(self, output_dir: Path) -> None:
        mock_query_response = MagicMock()
        mock_query_response.status_code = 200
        mock_query_response.raise_for_status = MagicMock()
        mock_query_response.json.return_value = {
            "data": {
                "hits": [
                    {
                        "file_id": "file-001",
                        "file_name": "test_counts.tsv.gz",
                        "file_size": 1024,
                        "cases": [{
                            "submitter_id": "TCGA-A1-A0SB",
                            "samples": [{"sample_type": "Primary Tumor"}],
                        }],
                    },
                ],
            },
        }

        mock_download_response = MagicMock()
        mock_download_response.status_code = 200
        mock_download_response.raise_for_status = MagicMock()
        mock_download_response.iter_content.return_value = [b"fake_data"]

        def mock_get(url, **kwargs):
            if "files" in url:
                return mock_query_response
            return mock_download_response

        with patch("requests.get", side_effect=mock_get):
            result = await download_tcga_data(
                project="TCGA-BRCA",
                output_dir=str(output_dir / "tcga_test"),
                max_files=1,
            )

        assert result["success"] is True
        assert result["project"] == "TCGA-BRCA"
        assert result["total_files_found"] == 1

    @pytest.mark.asyncio
    async def test_no_files_found(self, output_dir: Path) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": {"hits": []}}

        with patch("requests.get", return_value=mock_response):
            result = await download_tcga_data(
                project="TCGA-NONEXIST",
                output_dir=str(output_dir / "tcga_empty"),
            )

        assert result["success"] is False
        assert "no files found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_gdc_query_failure(self, output_dir: Path) -> None:
        with patch("requests.get", side_effect=ConnectionError("GDC down")):
            result = await download_tcga_data(
                project="TCGA-BRCA",
                output_dir=str(output_dir / "tcga_fail"),
            )

        assert result["success"] is False
        assert "failed" in result["error"].lower()
