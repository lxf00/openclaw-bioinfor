"""Tests for data validation checkpoints."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from bioopenclaw.mcp_servers.data_agent.tools.validators import (
    detect_data_unit,
    detect_log_state,
    validate_anndata_integrity,
    validate_batch_key,
    validate_checksum,
    validate_file_exists,
    validate_qc_result,
)


class TestFileValidators:
    def test_file_exists_ok(self, small_h5ad: Path) -> None:
        result = validate_file_exists(str(small_h5ad))
        assert result["valid"] is True

    def test_file_not_found(self) -> None:
        result = validate_file_exists("/nonexistent/file.h5ad")
        assert result["valid"] is False
        assert "not found" in result["message"].lower()

    def test_checksum_computes(self, small_h5ad: Path) -> None:
        result = validate_checksum(str(small_h5ad))
        assert result["valid"] is True
        assert "checksum" in result
        assert result["checksum"].startswith("sha256:")

    def test_checksum_mismatch(self, small_h5ad: Path) -> None:
        result = validate_checksum(str(small_h5ad), expected="wrong_hash")
        assert result["valid"] is False
        assert "mismatch" in result["message"].lower()


class TestLogStateDetection:
    def test_raw_counts_detected(self) -> None:
        import anndata as ad

        counts = np.random.poisson(50, (100, 200)).astype(np.float32)
        adata = ad.AnnData(X=counts)
        result = detect_log_state(adata)
        assert result["valid"] is True
        assert result["is_log_transformed"] is False
        assert result["max_value"] >= 30

    def test_logged_data_detected(self) -> None:
        import anndata as ad

        logged = np.random.uniform(0, 10, (50, 100)).astype(np.float32)
        adata = ad.AnnData(X=logged)
        result = detect_log_state(adata)
        assert result["valid"] is True
        assert result["is_log_transformed"] is True

    def test_high_value_counts_not_logged(self) -> None:
        import anndata as ad

        counts = np.random.poisson(100, (50, 100)).astype(np.float32)
        adata = ad.AnnData(X=counts)
        result = detect_log_state(adata)
        assert result["valid"] is True
        assert result["is_log_transformed"] is False


class TestDataUnitDetection:
    def test_counts_detected(self) -> None:
        import anndata as ad

        counts = np.array([[100, 0, 50], [200, 10, 0]], dtype=np.float32)
        adata = ad.AnnData(X=counts)
        result = detect_data_unit(adata)
        assert result["valid"] is True
        assert result["unit"] == "counts"

    def test_log_transformed_detected(self) -> None:
        import anndata as ad

        logged = np.random.uniform(0, 8, (50, 100)).astype(np.float32)
        adata = ad.AnnData(X=logged)
        result = detect_data_unit(adata)
        assert result["valid"] is True
        assert "log" in result["unit"].lower()


class TestBatchKeyValidation:
    def test_valid_batch_key(self, small_adata) -> None:
        result = validate_batch_key(small_adata, "batch")
        assert result["valid"] is True
        assert result["n_batches"] == 2

    def test_missing_batch_key(self, small_adata) -> None:
        result = validate_batch_key(small_adata, "nonexistent_key")
        assert result["valid"] is False
        assert "not found" in result["message"]

    def test_single_batch(self) -> None:
        import anndata as ad

        adata = ad.AnnData(
            X=np.zeros((10, 5)),
            obs={"batch": ["A"] * 10},
        )
        result = validate_batch_key(adata, "batch")
        assert result["valid"] is False
        assert "only 1" in result["message"].lower()


class TestAnndataIntegrity:
    def test_valid_adata(self, small_adata) -> None:
        result = validate_anndata_integrity(small_adata)
        assert result["valid"] is True
        assert result["n_obs"] == 200
        assert result["n_vars"] == 500

    def test_empty_adata(self) -> None:
        import anndata as ad

        adata = ad.AnnData(X=np.zeros((0, 0)))
        result = validate_anndata_integrity(adata)
        assert result["valid"] is False


class TestQCResult:
    def test_acceptable_result(self) -> None:
        result = validate_qc_result(cells_after=5000, genes_after=15000)
        assert result["valid"] is True

    def test_too_few_cells(self) -> None:
        result = validate_qc_result(cells_after=100, genes_after=15000)
        assert result["valid"] is False
        assert "100" in result["message"]

    def test_too_few_genes(self) -> None:
        result = validate_qc_result(cells_after=5000, genes_after=500)
        assert result["valid"] is False
        assert "500" in result["message"]
