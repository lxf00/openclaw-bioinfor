"""Watcher configuration using pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class WatcherConfig(BaseSettings):
    """Configuration for the Watcher engine and MCP Server.

    All settings can be overridden via environment variables prefixed with
    ``WATCHER_``. For example, ``WATCHER_HASH_WINDOW=15``.
    """

    model_config = SettingsConfigDict(
        env_prefix="WATCHER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Service ---
    port: int = 8005
    server_name: str = "watcher-tools"

    # --- Level 1: Repeated tool call detection ---
    hash_window: int = 10
    repeat_threshold: int = 3
    max_tool_rounds: int = 50

    # --- Level 2: Output stagnation detection ---
    similarity_threshold: float = 0.95
    stall_window: int = 5

    # --- Paths ---
    agents_dir: str = "./agents"
    inbox_dir: str = "./shared_memory/inbox"
    corrections_log_dir: str = "./agents/watcher/corrections_log"

    def ensure_dirs(self) -> None:
        """Create all necessary directories."""
        for d in (self.inbox_dir, self.corrections_log_dir):
            Path(d).mkdir(parents=True, exist_ok=True)


_config: WatcherConfig | None = None


def get_config() -> WatcherConfig:
    """Return the singleton config instance (lazy-loaded)."""
    global _config
    if _config is None:
        _config = WatcherConfig()
    return _config
