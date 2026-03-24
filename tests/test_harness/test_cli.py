from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from bioopenclaw.harness.cli import run_cli


def _write_active_context(path: Path) -> None:
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


@pytest.mark.asyncio
async def test_cli_start_command_persists_run(tmp_path: Path) -> None:
    for agent in ["scout_agent", "research_agent", "data_agent", "model_agent", "watcher"]:
        _write_active_context(tmp_path / "agents" / agent / "active_context.md")

    tool_map_path = tmp_path / "tool_map.json"
    tool_map_path.write_text(
        """
{
  "scout_agent": {
    "tool_name": "register_model",
    "tool_args": {
      "model_id": "org/demo-model",
      "name": "Demo Model"
    }
  },
  "research_agent": {
    "tool_name": "generate_hypothesis",
    "tool_args": {
      "background": "Perturbation changes cell states.",
      "observation": "Marker score shifts after treatment."
    }
  },
  "data_agent": {
    "tool_name": "inspect_dataset",
    "tool_args": {
      "file_path": "missing.h5ad"
    }
  },
  "model_agent": {
    "tool_name": "create_lora_config",
    "tool_args": {
      "base_model": "scGPT"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )

    payload = await run_cli(
        Namespace(
            project_root=str(tmp_path),
            state_root=None,
            transport="direct",
            tool_map=str(tool_map_path),
            command="start",
            title="CLI start task",
            goal="Create a persistent harness task from the CLI.",
            success_criteria=["task created"],
            priority="medium",
            constraints=None,
            inputs=None,
            requested_by="test",
            auto_run=False,
            max_ticks=5,
        )
    )

    assert payload["run_id"].startswith("run_")
    assert payload["status"] == "running"
    assert (tmp_path / ".harness_state" / "runs" / payload["run_id"] / "run.json").exists()
