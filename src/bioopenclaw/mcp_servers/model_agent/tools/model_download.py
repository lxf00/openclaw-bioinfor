"""Model download — HuggingFace Hub snapshot_download wrapper."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.model_agent.config import get_config

logger = logging.getLogger(__name__)


async def download_model(
    model_id: str,
    output_dir: str | None = None,
    revision: str = "main",
    allow_patterns: list[str] | None = None,
    ignore_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """Download a model from HuggingFace Hub.

    Uses ``huggingface_hub.snapshot_download`` for efficient downloading
    with resume support.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        return {
            "success": False,
            "error": "huggingface_hub not installed: pip install huggingface_hub",
        }

    cfg = get_config()
    target_dir = output_dir or str(Path(cfg.models_dir) / model_id.replace("/", "_"))

    if ignore_patterns is None:
        ignore_patterns = ["*.safetensors.index.json", "*.md", "*.txt"]

    logger.info("Downloading model %s (rev=%s) to %s", model_id, revision, target_dir)

    try:
        local_dir = snapshot_download(
            repo_id=model_id,
            local_dir=target_dir,
            revision=revision,
            token=cfg.hf_token or None,
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
        )

        downloaded_files = list(Path(local_dir).rglob("*"))
        file_count = sum(1 for f in downloaded_files if f.is_file())
        total_size_mb = sum(f.stat().st_size for f in downloaded_files if f.is_file()) / (1024 * 1024)

        logger.info("Download complete: %d files, %.1f MB", file_count, total_size_mb)

        return {
            "success": True,
            "model_id": model_id,
            "revision": revision,
            "local_dir": str(local_dir),
            "file_count": file_count,
            "total_size_mb": round(total_size_mb, 1),
        }
    except Exception as e:
        logger.error("Model download failed: %s", e)
        return {"success": False, "error": str(e), "model_id": model_id}
