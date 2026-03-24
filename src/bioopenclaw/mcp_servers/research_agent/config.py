"""Research Agent configuration using pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ResearchAgentConfig(BaseSettings):
    """Configuration for the Research Agent MCP Server.

    All settings can be overridden via environment variables prefixed with
    ``RESEARCH_AGENT_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="RESEARCH_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Service ---
    port: int = 8003
    server_name: str = "research-agent-tools"

    # --- External APIs ---
    entrez_email: str = ""
    ncbi_api_key: str = ""

    # --- Paths ---
    literature_dir: str = "shared_memory/literature"
    experiments_dir: str = "shared_memory/experiments"
    inbox_dir: str = "shared_memory/inbox"

    # --- Defaults ---
    default_max_results: int = 20
    default_significance_level: float = 0.05

    def ensure_dirs(self) -> None:
        """Create necessary directories."""
        for d in (self.literature_dir, self.experiments_dir, self.inbox_dir):
            Path(d).mkdir(parents=True, exist_ok=True)


_config: ResearchAgentConfig | None = None


def get_config() -> ResearchAgentConfig:
    """Return the singleton config instance (lazy-loaded)."""
    global _config
    if _config is None:
        _config = ResearchAgentConfig()
    return _config
