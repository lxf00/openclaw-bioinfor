"""Tests for intelligent dataset search (mock-based)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bioopenclaw.mcp_servers.data_agent.tools.dataset_search import search_datasets


class TestSearchDatasets:
    @pytest.mark.asyncio
    async def test_returns_success_structure(self) -> None:
        with patch(
            "bioopenclaw.mcp_servers.data_agent.tools.dataset_search._search_geo",
            return_value=[],
        ), patch(
            "bioopenclaw.mcp_servers.data_agent.tools.dataset_search._search_tcga",
            return_value=[],
        ), patch(
            "bioopenclaw.mcp_servers.data_agent.tools.dataset_search._search_cellxgene",
            return_value=[],
        ):
            result = await search_datasets(keywords=["BRCA1", "breast cancer"])

        assert result["success"] is True
        assert "datasets" in result
        assert "query" in result
        assert result["query"]["keywords"] == ["BRCA1", "breast cancer"]

    @pytest.mark.asyncio
    async def test_merges_results_from_sources(self) -> None:
        geo_results = [
            {"source": "GEO", "id": "GSE123", "title": "Test GEO", "sample_count": 50},
        ]
        tcga_results = [
            {"source": "TCGA", "id": "TCGA-BRCA", "title": "TCGA Breast", "sample_count": 1000},
        ]

        with patch(
            "bioopenclaw.mcp_servers.data_agent.tools.dataset_search._search_geo",
            return_value=geo_results,
        ), patch(
            "bioopenclaw.mcp_servers.data_agent.tools.dataset_search._search_tcga",
            return_value=tcga_results,
        ), patch(
            "bioopenclaw.mcp_servers.data_agent.tools.dataset_search._search_cellxgene",
            return_value=[],
        ):
            result = await search_datasets(keywords=["breast cancer"])

        assert result["total_found"] == 2
        assert result["datasets"][0]["source"] == "TCGA"
        assert result["datasets"][0]["sample_count"] == 1000

    @pytest.mark.asyncio
    async def test_single_source_filter(self) -> None:
        with patch(
            "bioopenclaw.mcp_servers.data_agent.tools.dataset_search._search_geo",
            return_value=[{"source": "GEO", "id": "GSE1", "sample_count": 10}],
        ):
            result = await search_datasets(
                keywords=["test"],
                sources=["geo"],
            )

        assert result["success"] is True
        assert result["total_found"] == 1

    @pytest.mark.asyncio
    async def test_invalid_source_returns_error(self) -> None:
        result = await search_datasets(keywords=["test"], sources=[])
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_no_results_gives_suggestion(self) -> None:
        with patch(
            "bioopenclaw.mcp_servers.data_agent.tools.dataset_search._search_geo",
            return_value=[],
        ):
            result = await search_datasets(keywords=["xyznonexistent"], sources=["geo"])

        assert result["total_found"] == 0
        assert "suggestion" in result
