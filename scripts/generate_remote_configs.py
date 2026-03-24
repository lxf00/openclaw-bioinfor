#!/usr/bin/env python3
"""Generate remote deployment config files for Harness + MCP servers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PLACEHOLDERS = ("__VENV_PY__", "__REPO_ROOT__", "__DATA_ROOT__", "__OPENCLAW_HOME__")


def replace_placeholders(text: str, mapping: dict[str, str]) -> str:
    """Replace known placeholder strings in *text* using *mapping*."""
    for key, value in mapping.items():
        text = text.replace(key, value)
    return text


def render_env_template(template_path: Path, output_path: Path, replacements: dict[str, str]) -> None:
    """Render ``.env`` from the checked-in template."""
    rendered = replace_placeholders(template_path.read_text(encoding="utf-8"), replacements)
    output_path.write_text(rendered, encoding="utf-8")


def render_mcp_config(
    source_path: Path,
    output_path: Path,
    replacements: dict[str, str],
    *,
    drop_legacy: bool = True,
) -> None:
    """Generate a server-ready MCP config with placeholders resolved."""
    raw = replace_placeholders(source_path.read_text(encoding="utf-8"), replacements)
    config = json.loads(raw)
    if drop_legacy:
        config.get("mcpServers", {}).pop("bioinformatics-tools", None)
    output_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def render_harness_tool_map(template_path: Path, output_path: Path) -> None:
    """Copy the default remote harness tool map into the target location."""
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate remote deployment configs")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--venv-py", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--openclaw-home", required=True)
    parser.add_argument("--keep-legacy-mcp", action="store_true")
    parser.add_argument("--env-output", type=Path, default=None)
    parser.add_argument("--mcp-output", type=Path, default=None)
    parser.add_argument("--tool-map-output", type=Path, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    repo_root = args.repo_root
    replacements = {
        "__VENV_PY__": args.venv_py,
        "__REPO_ROOT__": str(repo_root),
        "__DATA_ROOT__": args.data_root,
        "__OPENCLAW_HOME__": args.openclaw_home,
    }

    env_output = args.env_output or repo_root / ".env"
    mcp_output = args.mcp_output or repo_root / "mcp_config.remote.json"
    tool_map_output = args.tool_map_output or repo_root / "deploy" / "harness_tool_map.remote.generated.json"

    render_env_template(repo_root / ".env.example", env_output, replacements)
    render_mcp_config(
        repo_root / "mcp_config.json",
        mcp_output,
        replacements,
        drop_legacy=not args.keep_legacy_mcp,
    )
    render_harness_tool_map(repo_root / "deploy" / "harness_tool_map.remote.json", tool_map_output)

    print(f"Rendered .env -> {env_output}")
    print(f"Rendered MCP config -> {mcp_output}")
    print(f"Rendered harness tool map -> {tool_map_output}")


if __name__ == "__main__":
    main()
