"""Scout Agent configuration using pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoutAgentConfig(BaseSettings):
    """Configuration for the Scout Agent MCP Server.

    All settings can be overridden via environment variables prefixed with
    ``SCOUT_AGENT_``. For example, ``SCOUT_AGENT_PORT=9004``.
    """

    model_config = SettingsConfigDict(
        env_prefix="SCOUT_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Service ---
    port: int = 8004
    server_name: str = "scout-agent-tools"

    # --- HuggingFace ---
    hf_token: str = ""
    hf_default_tags: list[str] = [
        "biology", "single-cell", "protein", "genomics",
        "scRNA", "scGPT", "ESM", "Geneformer",
    ]
    hf_default_authors: list[str] = [
        "facebook", "bowang-lab", "ctheodoris", "InstaDeepAI",
    ]
    hf_scan_days_back: int = 7
    hf_scan_limit: int = 50

    # --- arXiv ---
    arxiv_categories: list[str] = [
        "q-bio.GN", "q-bio.QM", "q-bio.BM", "cs.LG",
    ]
    arxiv_max_results: int = 30

    # --- Model Registry ---
    registry_dir: str = "shared_memory/model_registry"
    inbox_dir: str = "shared_memory/inbox"

    def ensure_dirs(self) -> None:
        """Create registry and inbox directories if they don't exist."""
        for d in (self.registry_dir, self.inbox_dir):
            Path(d).mkdir(parents=True, exist_ok=True)


_config: ScoutAgentConfig | None = None


def get_config() -> ScoutAgentConfig:
    """Return the singleton config instance (lazy-loaded)."""
    global _config
    if _config is None:
        _config = ScoutAgentConfig()
    return _config
