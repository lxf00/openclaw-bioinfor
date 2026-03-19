"""Tests for PDB query tool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bioopenclaw.mcp_servers.data_agent.tools.pdb_query import query_pdb


class TestQueryPdb:
    @pytest.mark.asyncio
    async def test_successful_search(self) -> None:
        mock_search = MagicMock()
        mock_search.status_code = 200
        mock_search.json.return_value = {
            "result_set": [
                {"identifier": "1BNA"},
                {"identifier": "4HHB"},
            ]
        }

        mock_detail = MagicMock()
        mock_detail.status_code = 200
        mock_detail.json.return_value = {
            "struct": {"title": "Test Structure"},
            "exptl": [{"method": "X-RAY DIFFRACTION"}],
            "rcsb_entry_info": {
                "resolution_combined": [2.0],
                "polymer_entity_count": 2,
            },
            "rcsb_accession_info": {"deposit_date": "2020-01-01"},
        }

        with patch("requests.post", return_value=mock_search), \
             patch("requests.get", return_value=mock_detail):
            result = await query_pdb(query="hemoglobin", max_results=2)

        assert result["success"] is True
        assert result["total_found"] == 2
        assert result["entries"][0]["pdb_id"] == "1BNA"

    @pytest.mark.asyncio
    async def test_no_results(self) -> None:
        mock_search = MagicMock()
        mock_search.status_code = 200
        mock_search.json.return_value = {"result_set": []}

        with patch("requests.post", return_value=mock_search):
            result = await query_pdb(query="nonexistent_xyz_12345")

        assert result["success"] is True
        assert result["total_found"] == 0

    @pytest.mark.asyncio
    async def test_api_failure(self) -> None:
        with patch("requests.post", side_effect=Exception("API down")):
            result = await query_pdb(query="BRCA1")

        assert result["success"] is False
        assert "API" in result["error"]

    @pytest.mark.asyncio
    async def test_resolution_filter(self) -> None:
        mock_search = MagicMock()
        mock_search.status_code = 200
        mock_search.json.return_value = {"result_set": []}

        with patch("requests.post", return_value=mock_search) as mock_post:
            await query_pdb(query="insulin", resolution_max=2.0)

        call_args = mock_post.call_args
        body = call_args[1]["json"]
        nodes = body["query"].get("nodes", [body["query"]])
        has_resolution = any(
            n.get("parameters", {}).get("attribute", "")
            == "rcsb_entry_info.resolution_combined"
            for n in nodes
        )
        assert has_resolution
