"""Data lineage tracking — records every tool operation as a JSON entry.

Usage from any tool::

    from bioopenclaw.mcp_servers.data_agent.tools.lineage import record_step

    record_step(
        project="BRCA1_scRNA",
        operation="run_scanpy_qc",
        input_path="data/raw/GSE123456/matrix.h5ad",
        output_path="data/processed/BRCA1_scRNA/qc.h5ad",
        params={"min_genes": 200},
        metrics={"cells_before": 10000, "cells_after": 8500},
    )
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.config import get_config

logger = logging.getLogger(__name__)


def _lineage_path(project: str) -> Path:
    cfg = get_config()
    return Path(cfg.lineage_dir) / f"{project}.json"


def _load(project: str) -> dict[str, Any]:
    p = _lineage_path(project)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"project": project, "lineage": []}


def _save(data: dict[str, Any]) -> None:
    p = _lineage_path(data["project"])
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_step(
    project: str,
    operation: str,
    *,
    input_path: str | None = None,
    output_path: str | None = None,
    params: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    checksum: str | None = None,
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    """Append a lineage step and return the entry."""
    data = _load(project)
    step_num = len(data["lineage"]) + 1

    entry: dict[str, Any] = {
        "step": step_num,
        "operation": operation,
        "input": input_path,
        "output": output_path,
        "params": params or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if metrics:
        entry["metrics"] = metrics
    if checksum:
        entry["checksum"] = checksum
    if duration_seconds is not None:
        entry["duration_seconds"] = round(duration_seconds, 2)

    data["lineage"].append(entry)
    _save(data)

    logger.info(
        "Lineage recorded: project=%s step=%d op=%s",
        project, step_num, operation,
    )
    return entry


def get_lineage(project: str) -> dict[str, Any]:
    """Return the full lineage record for a project."""
    return _load(project)


class LineageTimer:
    """Context manager that measures elapsed time for a lineage step.

    Usage::

        with LineageTimer() as timer:
            # ... do work ...
        record_step(..., duration_seconds=timer.elapsed)
    """

    def __init__(self) -> None:
        self.start: float = 0
        self.elapsed: float = 0

    def __enter__(self) -> LineageTimer:
        self.start = time.monotonic()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.elapsed = time.monotonic() - self.start
