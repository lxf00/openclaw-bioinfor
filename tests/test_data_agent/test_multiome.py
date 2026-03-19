"""Tests for multi-omics processing tool."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

muon = pytest.importorskip("muon", reason="muon not installed")


def _make_mudata(tmp_path: Path) -> Path:
    """Create a synthetic MuData .h5mu file for testing."""
    import anndata as ad

    n_cells = 100
    obs_names = [f"cell_{i}" for i in range(n_cells)]

    rna = ad.AnnData(
        X=np.random.poisson(5, (n_cells, 200)).astype(np.float32),
        obs={"cell_id": obs_names},
    )
    rna.obs_names = obs_names
    rna.var_names = [f"Gene_{i}" for i in range(200)]
    rna.var_names = [("MT-" + rna.var_names[i] if i < 5 else rna.var_names[i]) for i in range(200)]

    adt = ad.AnnData(
        X=np.random.poisson(50, (n_cells, 20)).astype(np.float32),
        obs={"cell_id": obs_names},
    )
    adt.obs_names = obs_names
    adt.var_names = [f"Protein_{i}" for i in range(20)]

    mdata = muon.MuData({"rna": rna, "adt": adt})
    out_path = tmp_path / "test.h5mu"
    mdata.write(out_path)
    return out_path


class TestProcessMultiome:
    @pytest.mark.asyncio
    async def test_basic_processing(self, tmp_path: Path) -> None:
        from bioopenclaw.mcp_servers.data_agent.tools.multiome_process import process_multiome

        h5mu = _make_mudata(tmp_path)
        output = tmp_path / "processed.h5mu"

        result = await process_multiome(
            input_paths={"mudata": str(h5mu)},
            output_path=str(output),
        )

        assert result["success"] is True
        assert "rna" in result["modalities"]
        assert "adt" in result["modalities"]
        assert output.exists()

    @pytest.mark.asyncio
    async def test_rna_qc_params(self, tmp_path: Path) -> None:
        from bioopenclaw.mcp_servers.data_agent.tools.multiome_process import process_multiome

        h5mu = _make_mudata(tmp_path)
        output = tmp_path / "qc.h5mu"

        result = await process_multiome(
            input_paths={"mudata": str(h5mu)},
            output_path=str(output),
            qc_rna={"min_genes": 5, "min_cells": 1, "mt_pct": 50.0},
        )

        assert result["success"] is True
        assert "rna" in result["modality_summaries"]
        assert result["modality_summaries"]["rna"]["qc_params"]["min_genes"] == 5

    @pytest.mark.asyncio
    async def test_invalid_modality(self, tmp_path: Path) -> None:
        from bioopenclaw.mcp_servers.data_agent.tools.multiome_process import process_multiome

        h5mu = _make_mudata(tmp_path)
        output = tmp_path / "bad.h5mu"

        result = await process_multiome(
            input_paths={"mudata": str(h5mu)},
            output_path=str(output),
            modalities=["nonexistent"],
        )

        assert result["success"] is False
        assert "nonexistent" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_muon_import(self) -> None:
        from bioopenclaw.mcp_servers.data_agent.tools.multiome_process import process_multiome

        with patch.dict("sys.modules", {"muon": None}):
            with patch("builtins.__import__", side_effect=ImportError("no muon")):
                result = await process_multiome(
                    input_paths={"mudata": "test.h5mu"},
                    output_path="out.h5mu",
                )

        assert result["success"] is False
        assert "muon" in result["error"].lower()
