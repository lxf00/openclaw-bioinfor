from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_remote_configs import render_env_template, render_harness_tool_map, render_mcp_config
from scripts.prepare_runtime_layout import ensure_runtime_dirs, map_state_surface
from scripts.run_harness_smoke import run_smoke


def test_prepare_runtime_layout_creates_dirs_and_copy_surface(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    (repo_root / "agents").mkdir(parents=True)
    (repo_root / "shared_memory").mkdir(parents=True)
    (repo_root / "agents" / "README.md").write_text("agents", encoding="utf-8")
    (repo_root / "shared_memory" / "_index.md").write_text("index", encoding="utf-8")

    created = ensure_runtime_dirs(data_root)
    actions = map_state_surface(repo_root, data_root, mode="copy")

    assert created
    assert (data_root / "agents" / "scout_agent" / "daily_log").exists()
    assert (data_root / "shared_memory" / "inbox" / "archive").exists()
    assert any(action.startswith("copied") for action in actions)


def test_generate_remote_configs_renders_expected_outputs(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".env.example").write_text(
        "DATA_AGENT_DATA_DIR=__DATA_ROOT__/data\nOPENCLAW=__OPENCLAW_HOME__\n",
        encoding="utf-8",
    )
    (repo_root / "mcp_config.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "data-agent": {"command": "__VENV_PY__", "args": ["-m", "x"], "cwd": "__REPO_ROOT__"},
                    "bioinformatics-tools": {"command": "__VENV_PY__", "args": ["legacy"], "cwd": "__REPO_ROOT__"},
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    deploy_dir = repo_root / "deploy"
    deploy_dir.mkdir()
    (deploy_dir / "harness_tool_map.remote.json").write_text(
        json.dumps({"research_agent": {"tool_name": "generate_hypothesis", "tool_args": {}}}, indent=2),
        encoding="utf-8",
    )

    replacements = {
        "__VENV_PY__": "/opt/bioopenclaw/.venv/bin/python",
        "__REPO_ROOT__": "/opt/bioopenclaw",
        "__DATA_ROOT__": "/data/bioopenclaw",
        "__OPENCLAW_HOME__": "/home/ubuntu/.openclaw",
    }
    env_output = repo_root / ".env"
    mcp_output = repo_root / "mcp_config.remote.json"
    tool_map_output = deploy_dir / "harness_tool_map.remote.generated.json"

    render_env_template(repo_root / ".env.example", env_output, replacements)
    render_mcp_config(repo_root / "mcp_config.json", mcp_output, replacements, drop_legacy=True)
    render_harness_tool_map(deploy_dir / "harness_tool_map.remote.json", tool_map_output)

    assert "/data/bioopenclaw/data" in env_output.read_text(encoding="utf-8")
    rendered_mcp = json.loads(mcp_output.read_text(encoding="utf-8"))
    assert "bioinformatics-tools" not in rendered_mcp["mcpServers"]
    assert rendered_mcp["mcpServers"]["data-agent"]["command"] == "/opt/bioopenclaw/.venv/bin/python"
    rendered_tool_map = json.loads(tool_map_output.read_text(encoding="utf-8"))
    assert rendered_tool_map["research_agent"]["tool_name"] == "generate_hypothesis"


def test_run_harness_smoke_reports_state(tmp_path: Path) -> None:
    for agent in ["scout_agent", "research_agent", "data_agent", "model_agent", "watcher"]:
        path = tmp_path / "agents" / agent / "active_context.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            """---
last_session: 2026-03-21T00:00:00
---

## Current Focus
（暂无）

## Blocked
（暂无）

## Next Steps
（暂无）

## Recent Decisions
（暂无）
""",
            encoding="utf-8",
        )

    tool_map = tmp_path / "tool_map.json"
    tool_map.write_text(
        json.dumps(
            {
                "research_agent": {
                    "tool_name": "generate_hypothesis",
                    "tool_args": {
                        "background": "Summarize recent findings.",
                        "observation": "A marker appears higher after treatment.",
                    },
                }
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    import argparse
    import asyncio

    payload = asyncio.run(
        run_smoke(
            argparse.Namespace(
                project_root=tmp_path,
                tool_map=tool_map,
                transport="direct",
                title="Smoke",
                goal="Generate a hypothesis",
                    constraints=None,
                    inputs=None,
                success_criteria=["report available"],
                max_ticks=2,
            )
        )
    )

    assert payload["run_id"].startswith("run_")
    assert payload["state_dir_exists"] is True
