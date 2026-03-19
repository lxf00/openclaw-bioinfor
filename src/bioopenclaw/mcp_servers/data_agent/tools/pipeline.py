"""Pipeline orchestration — runs multi-step data processing workflows.

Each step calls an existing tool and automatically passes output paths
from the previous step as input to the next. Full lineage is recorded.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.config import get_config
from bioopenclaw.mcp_servers.data_agent.tools.lineage import record_step

logger = logging.getLogger(__name__)

AVAILABLE_STEPS = {
    "download_geo_data",
    "download_tcga_data",
    "query_cellxgene",
    "inspect_dataset",
    "run_scanpy_qc",
    "normalize_data",
    "convert_data_format",
    "run_batch_correction",
    "generate_qc_report",
}


async def run_pipeline(
    pipeline_config: dict[str, Any],
) -> dict[str, Any]:
    """Execute a multi-step data processing pipeline.

    Config format::

        {
          "name": "BRCA1_scRNA_processing",
          "project": "BRCA1_scRNA",
          "steps": [
            {"tool": "download_geo_data", "params": {"gse_id": "GSE123456"}},
            {"tool": "run_scanpy_qc", "params": {"min_genes": 200}},
            {"tool": "generate_qc_report", "params": {}},
          ],
          "output_dir": "./data/processed/BRCA1"
        }

    The pipeline automatically chains steps: each step's ``output_path``
    becomes the next step's ``input_path``.
    """
    name = pipeline_config.get("name", "unnamed_pipeline")
    project = pipeline_config.get("project", name)
    steps = pipeline_config.get("steps", [])
    output_dir = pipeline_config.get("output_dir")

    if not steps:
        return {"success": False, "error": "Pipeline has no steps defined"}

    unknown = [s["tool"] for s in steps if s.get("tool") not in AVAILABLE_STEPS]
    if unknown:
        return {
            "success": False,
            "error": f"Unknown tools in pipeline: {unknown}. Available: {sorted(AVAILABLE_STEPS)}",
        }

    cfg = get_config()
    if output_dir is None:
        output_dir = str(Path(cfg.processed_data_dir) / project)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Lazy-import all tool handlers
    from bioopenclaw.mcp_servers.data_agent.tools.batch_correction import run_batch_correction
    from bioopenclaw.mcp_servers.data_agent.tools.cellxgene_query import query_cellxgene
    from bioopenclaw.mcp_servers.data_agent.tools.data_inspector import inspect_dataset
    from bioopenclaw.mcp_servers.data_agent.tools.format_converter import convert_data_format
    from bioopenclaw.mcp_servers.data_agent.tools.geo_download import download_geo_data
    from bioopenclaw.mcp_servers.data_agent.tools.normalize import normalize_data
    from bioopenclaw.mcp_servers.data_agent.tools.qc_report import generate_qc_report
    from bioopenclaw.mcp_servers.data_agent.tools.scanpy_qc import run_scanpy_qc
    from bioopenclaw.mcp_servers.data_agent.tools.tcga_download import download_tcga_data

    handlers: dict[str, Any] = {
        "download_geo_data": download_geo_data,
        "download_tcga_data": download_tcga_data,
        "query_cellxgene": query_cellxgene,
        "inspect_dataset": inspect_dataset,
        "run_scanpy_qc": run_scanpy_qc,
        "normalize_data": normalize_data,
        "convert_data_format": convert_data_format,
        "run_batch_correction": run_batch_correction,
        "generate_qc_report": generate_qc_report,
    }

    logger.info("Pipeline '%s' starting: %d steps", name, len(steps))
    pipeline_start = time.monotonic()

    step_results: list[dict[str, Any]] = []
    last_output_path: str | None = None
    failed = False

    for i, step_def in enumerate(steps):
        tool_name = step_def["tool"]
        params = dict(step_def.get("params", {}))

        # Auto-chain: inject input_path/file_path from previous step
        if last_output_path:
            if tool_name == "inspect_dataset" and "file_path" not in params:
                params["file_path"] = last_output_path
            elif tool_name != "inspect_dataset" and "input_path" not in params and tool_name in (
                "run_scanpy_qc", "normalize_data", "run_batch_correction",
                "convert_data_format", "generate_qc_report",
            ):
                params["input_path"] = last_output_path

        # Auto-generate output_path if not provided
        if "output_path" not in params and tool_name in (
            "run_scanpy_qc", "normalize_data", "run_batch_correction",
            "convert_data_format",
        ):
            params["output_path"] = str(
                Path(output_dir) / f"step{i + 1}_{tool_name}.h5ad"
            )

        # Inject project for lineage tracking
        if "project" not in params and "project_name" not in params:
            if tool_name == "download_tcga_data":
                params["project_name"] = project
            elif tool_name != "inspect_dataset":
                params["project"] = project

        logger.info("Step %d/%d: %s", i + 1, len(steps), tool_name)
        step_start = time.monotonic()

        handler = handlers[tool_name]
        result = await handler(**params)

        step_elapsed = time.monotonic() - step_start

        step_record = {
            "step": i + 1,
            "tool": tool_name,
            "params": params,
            "success": result.get("success", False),
            "duration_seconds": round(step_elapsed, 2),
        }

        if not result.get("success"):
            step_record["error"] = result.get("error", "Unknown error")
            step_results.append(step_record)
            failed = True
            logger.error("Step %d failed: %s", i + 1, result.get("error"))
            break

        # Extract output path for chaining
        new_output = (
            result.get("output_path")
            or result.get("output_dir")
            or result.get("merged_path")
        )
        if new_output:
            last_output_path = new_output
            step_record["output_path"] = new_output

        # Capture key metrics
        for key in ("filtered_cells", "n_cells", "n_genes", "total_found", "files_downloaded"):
            if key in result:
                step_record[key] = result[key]

        step_results.append(step_record)
        logger.info("Step %d complete (%.1fs)", i + 1, step_elapsed)

    pipeline_elapsed = time.monotonic() - pipeline_start

    # Record pipeline-level lineage
    record_step(
        project=project,
        operation="run_pipeline",
        params={
            "pipeline_name": name,
            "total_steps": len(steps),
            "completed_steps": len(step_results),
        },
        metrics={
            "success": not failed,
            "final_output": last_output_path,
        },
        duration_seconds=pipeline_elapsed,
    )

    # Write experiment record
    _write_experiment_record(name, project, step_results, failed, pipeline_elapsed, last_output_path)

    pipeline_result: dict[str, Any] = {
        "success": not failed,
        "pipeline_name": name,
        "project": project,
        "total_steps": len(steps),
        "completed_steps": len(step_results),
        "steps": step_results,
        "final_output_path": last_output_path,
        "duration_seconds": round(pipeline_elapsed, 2),
    }

    if failed:
        pipeline_result["error"] = f"Pipeline failed at step {len(step_results)}"

    logger.info(
        "Pipeline '%s' %s: %d/%d steps in %.1fs",
        name, "completed" if not failed else "FAILED",
        len(step_results), len(steps), pipeline_elapsed,
    )
    return pipeline_result


def _write_experiment_record(
    name: str,
    project: str,
    step_results: list[dict[str, Any]],
    failed: bool,
    elapsed: float,
    final_output: str | None,
) -> None:
    """Write an experiment record to shared_memory/experiments/."""
    experiments_dir = Path("shared_memory/experiments")
    experiments_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    safe_name = name.replace(" ", "_").replace("/", "_")[:50]
    record_path = experiments_dir / f"{today}_{safe_name}.md"

    # Extract cell_count from the last successful step
    cell_count = "N/A"
    for sr in reversed(step_results):
        if sr.get("success"):
            for key in ("filtered_cells", "n_cells"):
                if key in sr:
                    cell_count = sr[key]
                    break
            if cell_count != "N/A":
                break

    lines = [
        "---",
        f"dataset: {project}",
        f"date: {today}",
        "processed_by: data_agent",
        f"status: {'completed' if not failed else 'failed'}",
        f"cell_count: {cell_count}",
        "---",
        "",
        f"# {name}",
        "",
        "## Pipeline Steps",
        "",
    ]

    for sr in step_results:
        status = "OK" if sr.get("success") else "FAILED"
        lines.append(f"- Step {sr['step']}: **{sr['tool']}** — {status} ({sr.get('duration_seconds', 0):.1f}s)")
        if sr.get("error"):
            lines.append(f"  - Error: {sr['error']}")
        if sr.get("output_path"):
            lines.append(f"  - Output: `{sr['output_path']}`")

    lines.extend([
        "",
        "## Summary",
        "",
        f"- Total duration: {elapsed:.1f}s",
        f"- Final output: `{final_output or 'N/A'}`",
        "",
    ])

    record_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Experiment record: %s", record_path)
