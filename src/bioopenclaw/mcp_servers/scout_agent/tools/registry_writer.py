"""Model registry writer — creates/updates model files in shared_memory/model_registry."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.scout_agent.config import get_config

logger = logging.getLogger(__name__)


async def register_model(
    model_id: str,
    name: str,
    version: str = "",
    model_type: str = "",
    parameters: str = "",
    license: str = "",
    architecture: str = "",
    modalities: list[str] | None = None,
    species: list[str] | None = None,
    paper_url: str | None = None,
    benchmarks: list[dict[str, Any]] | None = None,
    limitations: list[str] | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Register a new model (or update an existing one) in model_registry.

    Creates ``shared_memory/model_registry/<safe_name>.md`` and appends an
    entry to ``shared_memory/model_registry/_index.md``.
    """
    cfg = get_config()
    registry_dir = Path(cfg.registry_dir)
    registry_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(name)
    model_file = registry_dir / f"{safe_name}.md"
    index_file = registry_dir / "_index.md"
    today = datetime.now().strftime("%Y-%m-%d")

    is_update = model_file.exists()

    try:
        content = _render_model_md(
            model_id=model_id,
            name=name,
            version=version,
            model_type=model_type,
            parameters=parameters,
            license_str=license,
            architecture=architecture,
            modalities=modalities or [],
            species=species or [],
            paper_url=paper_url,
            benchmarks=benchmarks or [],
            limitations=limitations or [],
            description=description,
            today=today,
        )

        model_file.write_text(content, encoding="utf-8")
        logger.info("Wrote model file: %s", model_file)

        _update_index(index_file, name, safe_name, model_type, parameters, today, is_update)

        action = "updated" if is_update else "registered"
        logger.info("Model %s: %s (%s)", action, name, model_id)

        return {
            "success": True,
            "action": action,
            "model_id": model_id,
            "name": name,
            "file_path": str(model_file),
            "index_updated": True,
        }

    except Exception as e:
        logger.error("Failed to register model %s: %s", name, e)
        return {"success": False, "error": str(e)}


def _safe_filename(name: str) -> str:
    """Convert a model name to a filesystem-safe filename."""
    safe = re.sub(r"[^\w\s-]", "", name)
    safe = re.sub(r"[\s]+", "_", safe).strip("_")
    return safe or "unnamed_model"


def _render_model_md(
    model_id: str,
    name: str,
    version: str,
    model_type: str,
    parameters: str,
    license_str: str,
    architecture: str,
    modalities: list[str],
    species: list[str],
    paper_url: str | None,
    benchmarks: list[dict[str, Any]],
    limitations: list[str],
    description: str,
    today: str,
) -> str:
    """Render a model registry Markdown file with YAML front matter."""
    modalities_yaml = ", ".join(modalities) if modalities else ""
    species_yaml = ", ".join(species) if species else ""

    lines = [
        "---",
        f"name: {name}",
        f'version: "{version}"',
        f"updated: {today}",
        f"source: https://huggingface.co/{model_id}",
    ]
    if paper_url:
        lines.append(f"paper: {paper_url}")
    lines.extend([
        f"license: {license_str}",
        f"parameters: {parameters}",
        f"architecture: {architecture}",
        f"modalities: [{modalities_yaml}]",
        f"species: [{species_yaml}]",
        f"type: {model_type}",
        "---",
        "",
        f"# {name}",
        "",
    ])

    if description:
        lines.extend([description, ""])

    lines.append("## Benchmarks")
    lines.append("")
    if benchmarks:
        lines.append("| Benchmark | Task | Score | Date |")
        lines.append("|-----------|------|-------|------|")
        for b in benchmarks:
            lines.append(
                f"| {b.get('benchmark', '')} | {b.get('task', '')} "
                f"| {b.get('score', '')} | {b.get('date', '')} |"
            )
    else:
        lines.append("*暂无基准测试数据*")
    lines.append("")

    lines.append("## Known Limitations")
    lines.append("")
    if limitations:
        for lim in limitations:
            lines.append(f"- {lim}")
    else:
        lines.append("*暂无*")
    lines.append("")

    lines.append("## Fine-tuning Notes")
    lines.append("")
    lines.append("*暂无*")
    lines.append("")

    lines.append("## BioOpenClaw Usage History")
    lines.append("")
    lines.append("*暂无使用记录*")
    lines.append("")

    return "\n".join(lines)


def _update_index(
    index_file: Path,
    name: str,
    safe_name: str,
    model_type: str,
    parameters: str,
    today: str,
    is_update: bool,
) -> None:
    """Add or update an entry in _index.md."""
    if not index_file.exists():
        index_file.write_text(
            "# Model Registry Index\n\n"
            "| Model | Type | Parameters | Updated | File |\n"
            "|-------|------|-----------|---------|------|\n",
            encoding="utf-8",
        )

    content = index_file.read_text(encoding="utf-8")
    entry_line = f"| {name} | {model_type} | {parameters} | {today} | `{safe_name}.md` |"

    if is_update:
        lines = content.split("\n")
        updated = False
        for i, line in enumerate(lines):
            if f"`{safe_name}.md`" in line:
                lines[i] = entry_line
                updated = True
                break
        if updated:
            index_file.write_text("\n".join(lines), encoding="utf-8")
            return

    if not content.endswith("\n"):
        content += "\n"
    content += entry_line + "\n"
    index_file.write_text(content, encoding="utf-8")
