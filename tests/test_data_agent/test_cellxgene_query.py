"""Tests for CellxGene Census query tool (mock-based)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bioopenclaw.mcp_servers.data_agent.tools.cellxgene_query import query_cellxgene


MOCK_COLLECTIONS = [
    {
        "collection_id": "coll-001",
        "name": "Human breast cancer atlas",
        "description": "Single cell atlas of breast cancer tumors",
        "published_at": "2025-06-15",
        "datasets": [
            {
                "cell_count": 500000,
                "organism": [{"label": "Homo sapiens"}],
                "tissue": [{"label": "breast"}],
                "disease": [{"label": "breast cancer"}],
                "assay": [{"label": "10x 3' v3"}],
            },
        ],
    },
    {
        "collection_id": "coll-002",
        "name": "Mouse brain atlas",
        "description": "Spatial transcriptomics of mouse brain",
        "published_at": "2025-01-10",
        "datasets": [
            {
                "cell_count": 200000,
                "organism": [{"label": "Mus musculus"}],
                "tissue": [{"label": "brain"}],
                "disease": [{"label": "normal"}],
                "assay": [{"label": "Slide-seq"}],
            },
        ],
    },
]


class TestQueryCellxGene:
    @pytest.mark.asyncio
    async def test_search_by_tissue(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = MOCK_COLLECTIONS

        with patch("requests.get", return_value=mock_resp):
            result = await query_cellxgene(tissue=["breast"])

        assert result["success"] is True
        assert result["total_found"] >= 1
        assert any("breast" in c.get("title", "").lower() for c in result["collections"])

    @pytest.mark.asyncio
    async def test_filter_by_organism(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = MOCK_COLLECTIONS

        with patch("requests.get", return_value=mock_resp):
            result = await query_cellxgene(
                organism="Mus musculus",
                tissue=["brain"],
            )

        assert result["success"] is True
        for coll in result["collections"]:
            assert "mouse" in coll["title"].lower() or "brain" in coll["title"].lower()

    @pytest.mark.asyncio
    async def test_api_failure(self) -> None:
        with patch("requests.get", side_effect=ConnectionError("API down")):
            result = await query_cellxgene(tissue=["breast"])

        assert result["success"] is False
        assert "failed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_download_mode_without_dep(self) -> None:
        result = await query_cellxgene(
            tissue=["breast"],
            download=True,
        )
        assert result["success"] is False
        assert "cellxgene-census" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_returns_collection_metadata(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = MOCK_COLLECTIONS

        with patch("requests.get", return_value=mock_resp):
            result = await query_cellxgene(disease=["breast cancer"])

        assert result["success"] is True
        if result["total_found"] > 0:
            coll = result["collections"][0]
            assert "collection_id" in coll
            assert "total_cells" in coll
            assert "url" in coll
