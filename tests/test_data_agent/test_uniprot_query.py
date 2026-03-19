"""Tests for UniProt query tool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bioopenclaw.mcp_servers.data_agent.tools.uniprot_query import query_uniprot


class TestQueryUniprot:
    @pytest.mark.asyncio
    async def test_successful_search(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "primaryAccession": "P38398",
                    "uniProtkbId": "BRCA1_HUMAN",
                    "proteinDescription": {
                        "recommendedName": {
                            "fullName": {"value": "Breast cancer type 1 susceptibility protein"}
                        }
                    },
                    "genes": [{"geneName": {"value": "BRCA1"}}],
                    "organism": {"scientificName": "Homo sapiens"},
                    "sequence": {"length": 1863},
                }
            ]
        }

        with patch("requests.get", return_value=mock_response):
            result = await query_uniprot(query="BRCA1", organism="Homo sapiens")

        assert result["success"] is True
        assert result["total_found"] == 1
        assert result["entries"][0]["accession"] == "P38398"
        assert result["entries"][0]["gene_names"] == ["BRCA1"]

    @pytest.mark.asyncio
    async def test_no_results(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch("requests.get", return_value=mock_response):
            result = await query_uniprot(query="nonexistent_xyz_protein_12345")

        assert result["success"] is True
        assert result["total_found"] == 0

    @pytest.mark.asyncio
    async def test_api_failure(self) -> None:
        with patch("requests.get", side_effect=Exception("Connection timeout")):
            result = await query_uniprot(query="BRCA1")

        assert result["success"] is False
        assert "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_reviewed_only_filter(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch("requests.get", return_value=mock_response) as mock_get:
            await query_uniprot(query="TP53", reviewed_only=True)

        call_args = mock_get.call_args
        query_str = call_args[1]["params"]["query"]
        assert "reviewed:true" in query_str
