"""Model Agent configuration using pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelAgentConfig(BaseSettings):
    """Configuration for the Model Agent MCP Server.

    All settings can be overridden via environment variables prefixed with
    ``MODEL_AGENT_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="MODEL_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Service ---
    port: int = 8002
    server_name: str = "model-agent-tools"

    # --- HuggingFace ---
    hf_token: str = ""

    # --- Paths ---
    models_dir: str = "./models"
    checkpoints_dir: str = "./models/checkpoints"
    configs_dir: str = "./models/configs"
    experiments_dir: str = "shared_memory/experiments"
    registry_dir: str = "shared_memory/model_registry"
    inbox_dir: str = "shared_memory/inbox"

    # --- LoRA defaults ---
    default_lora_rank: int = 8
    default_lora_alpha: int = 16
    default_learning_rate: float = 2e-4
    default_epochs: int = 10
    default_batch_size: int = 8

    def ensure_dirs(self) -> None:
        """Create necessary directories."""
        for d in (self.models_dir, self.checkpoints_dir, self.configs_dir):
            Path(d).mkdir(parents=True, exist_ok=True)


_config: ModelAgentConfig | None = None


def get_config() -> ModelAgentConfig:
    """Return the singleton config instance (lazy-loaded)."""
    global _config
    if _config is None:
        _config = ModelAgentConfig()
    return _config
