"""Data Agent configuration using pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataAgentConfig(BaseSettings):
    """Configuration for the Data Agent MCP Server.

    All settings can be overridden via environment variables prefixed with
    ``DATA_AGENT_``. For example, ``DATA_AGENT_PORT=9000``.
    """

    model_config = SettingsConfigDict(
        env_prefix="DATA_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Service ---
    port: int = 8001
    server_name: str = "data-agent-tools"

    # --- Data storage (local or remote paths) ---
    data_dir: str = "./data"
    raw_data_dir: str = "./data/raw"
    processed_data_dir: str = "./data/processed"
    reports_dir: str = "./data/reports"
    lineage_dir: str = "./data/lineage"
    max_file_size_gb: float = 10.0

    # --- External APIs ---
    entrez_email: str = ""
    ncbi_api_key: str = ""

    # --- Network & retry ---
    download_timeout_seconds: int = 3600
    download_max_retries: int = 3
    download_retry_delay_seconds: int = 30
    api_rate_limit_per_second: float = 3.0

    # --- QC defaults ---
    default_organism: str = "Homo sapiens"
    default_qc_min_genes: int = 200
    default_qc_min_cells: int = 3
    default_qc_mt_pct: float = 20.0
    default_batch_method: str = "harmony"

    # --- Derived helpers (not env-configurable) ---

    def ensure_dirs(self) -> None:
        """Create all data directories if they don't exist."""
        for d in (
            self.raw_data_dir,
            self.processed_data_dir,
            self.reports_dir,
            self.lineage_dir,
        ):
            Path(d).mkdir(parents=True, exist_ok=True)

    @field_validator("entrez_email")
    @classmethod
    def _warn_empty_email(cls, v: str) -> str:
        if not v:
            import warnings
            warnings.warn(
                "DATA_AGENT_ENTREZ_EMAIL is empty. "
                "NCBI API calls (GEO download, literature search) will fail. "
                "Set it via env var or .env file.",
                stacklevel=2,
            )
        return v


_config: DataAgentConfig | None = None


def get_config() -> DataAgentConfig:
    """Return the singleton config instance (lazy-loaded)."""
    global _config
    if _config is None:
        _config = DataAgentConfig()
    return _config
