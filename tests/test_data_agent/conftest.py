"""Shared fixtures for Data Agent tests.

Provides offline-first test data using Scanpy's built-in pbmc3k dataset
(small subset) so that no network access is needed for unit tests.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--online",
        action="store_true",
        default=False,
        help="Run tests that require network access (marked @pytest.mark.online)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if not config.getoption("--online"):
        skip_online = pytest.mark.skip(reason="need --online flag to run")
        for item in items:
            if "online" in item.keywords:
                item.add_marker(skip_online)


@pytest.fixture(scope="session")
def tmp_data_dir() -> Path:
    """Session-scoped temporary directory for test data."""
    d = Path(tempfile.mkdtemp(prefix="bioopenclaw_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def small_adata(tmp_data_dir: Path):
    """Create a small synthetic AnnData object mimicking pbmc3k.

    200 cells x 500 genes, with MT- genes and batch info.
    """
    import anndata as ad
    from scipy.sparse import csr_matrix

    rng = np.random.default_rng(42)
    n_cells, n_genes = 200, 500

    counts = rng.poisson(lam=2, size=(n_cells, n_genes)).astype(np.float32)
    counts[counts > 10] = 10

    gene_names = [f"Gene_{i}" for i in range(n_genes)]
    gene_names[0] = "MT-CO1"
    gene_names[1] = "MT-ND1"
    gene_names[2] = "MT-ATP6"

    cell_names = [f"Cell_{i}" for i in range(n_cells)]
    batch_labels = rng.choice(["batch_A", "batch_B"], size=n_cells)

    adata = ad.AnnData(
        X=csr_matrix(counts),
        obs={"batch": batch_labels},
        var={"gene_name": gene_names},
    )
    adata.obs_names = cell_names
    adata.var_names = gene_names

    return adata


@pytest.fixture
def small_h5ad(small_adata, tmp_data_dir: Path) -> Path:
    """Write the small AnnData to a .h5ad file and return the path."""
    p = tmp_data_dir / "test_input.h5ad"
    if not p.exists():
        small_adata.write_h5ad(p)
    return p


@pytest.fixture
def logged_h5ad(tmp_data_dir: Path) -> Path:
    """Create a .h5ad file with log-transformed data (max < 15)."""
    import anndata as ad

    rng = np.random.default_rng(99)
    n_cells, n_genes = 100, 300
    logged_data = rng.uniform(0, 10, size=(n_cells, n_genes)).astype(np.float32)

    gene_names = [f"Gene_{i}" for i in range(n_genes)]
    gene_names[0] = "MT-CO1"

    adata = ad.AnnData(
        X=logged_data,
        var={"gene_name": gene_names},
    )
    adata.var_names = gene_names
    adata.obs_names = [f"Cell_{i}" for i in range(n_cells)]

    p = tmp_data_dir / "test_logged.h5ad"
    adata.write_h5ad(p)
    return p


@pytest.fixture
def output_dir(tmp_data_dir: Path) -> Path:
    """Return a clean output directory for each test."""
    d = tmp_data_dir / "output"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture(autouse=True)
def _set_test_config(tmp_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Override config to use temp directories."""
    monkeypatch.setenv("DATA_AGENT_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("DATA_AGENT_RAW_DATA_DIR", str(tmp_data_dir / "raw"))
    monkeypatch.setenv("DATA_AGENT_PROCESSED_DATA_DIR", str(tmp_data_dir / "processed"))
    monkeypatch.setenv("DATA_AGENT_REPORTS_DIR", str(tmp_data_dir / "reports"))
    monkeypatch.setenv("DATA_AGENT_LINEAGE_DIR", str(tmp_data_dir / "lineage"))
    monkeypatch.setenv("DATA_AGENT_ENTREZ_EMAIL", "test@example.com")

    from bioopenclaw.mcp_servers.data_agent import config
    config._config = None
