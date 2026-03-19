"""Tests for local data version manager."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from bioopenclaw.mcp_servers.data_agent.tools.version_manager import (
    create_snapshot,
    list_versions,
    restore_version,
)


@pytest.fixture
def sample_h5ad(tmp_path: Path) -> Path:
    """Create a small .h5ad file for versioning tests."""
    import anndata as ad

    adata = ad.AnnData(X=np.random.rand(50, 30).astype(np.float32))
    adata.obs_names = [f"cell_{i}" for i in range(50)]
    adata.var_names = [f"gene_{i}" for i in range(30)]
    path = tmp_path / "test_data.h5ad"
    adata.write_h5ad(path)
    return path


class TestCreateSnapshot:
    @pytest.mark.asyncio
    async def test_creates_snapshot(self, sample_h5ad: Path) -> None:
        result = await create_snapshot(
            file_path=str(sample_h5ad),
            project="test_proj",
            tag="v1",
            description="initial version",
        )

        assert result["success"] is True
        assert result["tag"] == "v1"
        assert Path(result["snapshot_path"]).exists()
        assert result["checksum"] is not None

    @pytest.mark.asyncio
    async def test_duplicate_tag_fails(self, sample_h5ad: Path) -> None:
        await create_snapshot(str(sample_h5ad), "dup_proj", "v1")
        result = await create_snapshot(str(sample_h5ad), "dup_proj", "v1")

        assert result["success"] is False
        assert "already exists" in result["error"]

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        result = await create_snapshot("/nonexistent.h5ad", "proj", "v1")
        assert result["success"] is False


class TestListVersions:
    @pytest.mark.asyncio
    async def test_list_empty(self) -> None:
        result = await list_versions("empty_project_xyz")
        assert result["success"] is True
        assert result["total_versions"] == 0

    @pytest.mark.asyncio
    async def test_list_after_snapshots(self, sample_h5ad: Path) -> None:
        await create_snapshot(str(sample_h5ad), "list_proj", "v1", "first")
        await create_snapshot(str(sample_h5ad), "list_proj", "v2", "second")

        result = await list_versions("list_proj")
        assert result["success"] is True
        assert result["total_versions"] == 2
        assert result["versions"][0]["tag"] == "v1"
        assert result["versions"][1]["tag"] == "v2"


class TestRestoreVersion:
    @pytest.mark.asyncio
    async def test_restore_to_custom_path(self, sample_h5ad: Path, tmp_path: Path) -> None:
        await create_snapshot(str(sample_h5ad), "restore_proj", "v1")

        restore_path = tmp_path / "restored" / "data.h5ad"
        result = await restore_version("restore_proj", "v1", str(restore_path))

        assert result["success"] is True
        assert result["checksum_verified"] is True
        assert restore_path.exists()

    @pytest.mark.asyncio
    async def test_restore_missing_tag(self) -> None:
        result = await restore_version("restore_proj2", "nonexistent")
        assert result["success"] is False
        assert "not found" in result["error"]
