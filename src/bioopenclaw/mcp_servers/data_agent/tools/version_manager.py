"""Local data version manager — Phase 1 substitute for lakeFS.

Provides snapshot/restore semantics via file copy + JSON index.
Each project has a ``_versions.json`` index in ``data/versions/<project>/``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.config import get_config
from bioopenclaw.mcp_servers.data_agent.tools.lineage import record_step

logger = logging.getLogger(__name__)


def _versions_dir(project: str) -> Path:
    cfg = get_config()
    base = Path(cfg.data_dir) / "versions" / project
    base.mkdir(parents=True, exist_ok=True)
    return base


def _index_path(project: str) -> Path:
    return _versions_dir(project) / "_versions.json"


def _load_index(project: str) -> list[dict[str, Any]]:
    idx = _index_path(project)
    if idx.exists():
        with open(idx, encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_index(project: str, entries: list[dict[str, Any]]) -> None:
    idx = _index_path(project)
    with open(idx, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def _file_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


async def create_snapshot(
    file_path: str,
    project: str,
    tag: str,
    description: str = "",
) -> dict[str, Any]:
    """Create a versioned snapshot of a data file.

    Copies the file to ``data/versions/<project>/<tag>/`` and records
    metadata (checksum, timestamp, source path) in a JSON index.
    """
    src = Path(file_path)
    if not src.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    tag_dir = _versions_dir(project) / tag
    if tag_dir.exists():
        return {
            "success": False,
            "error": f"Tag '{tag}' already exists for project '{project}'. Use a different tag.",
        }

    tag_dir.mkdir(parents=True)
    dest = tag_dir / src.name
    shutil.copy2(str(src), str(dest))

    checksum = _file_checksum(dest)
    size_bytes = dest.stat().st_size

    entry = {
        "tag": tag,
        "source_path": str(src.absolute()),
        "snapshot_path": str(dest.absolute()),
        "file_name": src.name,
        "checksum_sha256": checksum,
        "size_bytes": size_bytes,
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    index = _load_index(project)
    index.append(entry)
    _save_index(project, index)

    record_step(
        project=project,
        operation="create_snapshot",
        input_path=file_path,
        output_path=str(dest.absolute()),
        params={"tag": tag, "description": description},
        checksum=f"sha256:{checksum}",
    )

    logger.info("Snapshot created: %s/%s → %s", project, tag, dest)
    return {
        "success": True,
        "project": project,
        "tag": tag,
        "snapshot_path": str(dest.absolute()),
        "checksum": checksum,
        "size_bytes": size_bytes,
    }


async def list_versions(
    project: str,
) -> dict[str, Any]:
    """List all version snapshots for a project."""
    index = _load_index(project)

    return {
        "success": True,
        "project": project,
        "total_versions": len(index),
        "versions": [
            {
                "tag": e["tag"],
                "file_name": e["file_name"],
                "size_bytes": e["size_bytes"],
                "created_at": e["created_at"],
                "description": e.get("description", ""),
            }
            for e in index
        ],
    }


async def restore_version(
    project: str,
    tag: str,
    restore_to: str | None = None,
) -> dict[str, Any]:
    """Restore a file from a version snapshot.

    If ``restore_to`` is not specified, the file is restored to its
    original source path.
    """
    index = _load_index(project)
    entry = next((e for e in index if e["tag"] == tag), None)

    if entry is None:
        available = [e["tag"] for e in index]
        return {
            "success": False,
            "error": f"Tag '{tag}' not found for project '{project}'. Available: {available}",
        }

    snapshot = Path(entry["snapshot_path"])
    if not snapshot.exists():
        return {
            "success": False,
            "error": f"Snapshot file missing: {snapshot}. Index may be corrupted.",
        }

    if restore_to is None:
        restore_to = entry["source_path"]

    dest = Path(restore_to)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(snapshot), str(dest))

    current_checksum = _file_checksum(dest)
    if current_checksum != entry["checksum_sha256"]:
        return {
            "success": False,
            "error": "Checksum mismatch after restore — file may be corrupted.",
        }

    logger.info("Version restored: %s/%s → %s", project, tag, dest)
    return {
        "success": True,
        "project": project,
        "tag": tag,
        "restored_to": str(dest.absolute()),
        "checksum_verified": True,
    }
