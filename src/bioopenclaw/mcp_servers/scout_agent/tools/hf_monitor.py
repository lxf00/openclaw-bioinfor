"""HuggingFace Hub monitoring — scans for new/updated bioinformatics models."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from bioopenclaw.mcp_servers.scout_agent.config import get_config

logger = logging.getLogger(__name__)


async def scan_huggingface_models(
    tags: list[str] | None = None,
    authors: list[str] | None = None,
    days_back: int = 7,
    limit: int = 50,
) -> dict[str, Any]:
    """Scan HuggingFace Hub for recently published/updated bioinformatics models.

    Searches by tags and/or authors, filtering to models modified within
    *days_back* days.  Returns structured metadata for each discovered model.
    """
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return {
            "success": False,
            "error": "huggingface_hub not installed. Run: pip install huggingface_hub",
        }

    cfg = get_config()
    if tags is None:
        tags = list(cfg.hf_default_tags)
    if authors is None:
        authors = list(cfg.hf_default_authors)

    api = HfApi(token=cfg.hf_token or None)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    discovered: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    try:
        for tag in tags:
            try:
                models = api.list_models(
                    search=tag,
                    sort="lastModified",
                    direction=-1,
                    limit=limit,
                )
                for m in models:
                    if m.id in seen_ids:
                        continue
                    last_modified = m.lastModified
                    if last_modified and last_modified < cutoff:
                        continue
                    seen_ids.add(m.id)
                    discovered.append(_model_to_dict(m))
            except Exception as e:
                logger.warning("HF search failed for tag '%s': %s", tag, e)

        for author in authors:
            try:
                models = api.list_models(
                    author=author,
                    sort="lastModified",
                    direction=-1,
                    limit=limit,
                )
                for m in models:
                    if m.id in seen_ids:
                        continue
                    last_modified = m.lastModified
                    if last_modified and last_modified < cutoff:
                        continue
                    seen_ids.add(m.id)
                    discovered.append(_model_to_dict(m))
            except Exception as e:
                logger.warning("HF search failed for author '%s': %s", author, e)

        discovered.sort(key=lambda x: x.get("last_modified", ""), reverse=True)
        discovered = discovered[:limit]

        logger.info(
            "HuggingFace scan complete: %d models found (tags=%s, authors=%s, days_back=%d)",
            len(discovered), tags, authors, days_back,
        )

        return {
            "success": True,
            "query": {
                "tags": tags,
                "authors": authors,
                "days_back": days_back,
                "limit": limit,
            },
            "total_found": len(discovered),
            "models": discovered,
        }

    except Exception as e:
        logger.error("HuggingFace scan failed: %s", e)
        return {"success": False, "error": str(e)}


def _model_to_dict(m: Any) -> dict[str, Any]:
    """Convert an HfApi ModelInfo object to a plain dict."""
    return {
        "model_id": m.id,
        "author": m.author or "",
        "tags": list(m.tags) if m.tags else [],
        "last_modified": m.lastModified.isoformat() if m.lastModified else "",
        "downloads": getattr(m, "downloads", 0) or 0,
        "likes": getattr(m, "likes", 0) or 0,
        "pipeline_tag": getattr(m, "pipeline_tag", "") or "",
        "library_name": getattr(m, "library_name", "") or "",
        "hf_url": f"https://huggingface.co/{m.id}",
    }
