#!/usr/bin/env python3
"""Run a Harness smoke task and inspect the projected state surface."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from bioopenclaw.harness.app import ProjectHarnessApp, load_json_mapping


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a BioOpenClaw harness smoke task")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--tool-map", type=Path, required=True)
    parser.add_argument("--transport", choices=["direct", "stdio"], default="direct")
    parser.add_argument("--title", default="Remote harness smoke")
    parser.add_argument(
        "--goal",
        default="Search literature and generate a first-pass hypothesis",
    )
    parser.add_argument("--constraints", type=Path, default=None)
    parser.add_argument("--inputs", type=Path, default=None)
    parser.add_argument(
        "--success-criterion",
        action="append",
        dest="success_criteria",
        default=["report available"],
    )
    parser.add_argument("--max-ticks", type=int, default=5)
    return parser


async def run_smoke(args: argparse.Namespace) -> dict[str, object]:
    app = ProjectHarnessApp.from_project(
        project_root=args.project_root,
        transport=args.transport,
        tool_selection=load_json_mapping(args.tool_map),
    )
    run = app.start_task(
        title=args.title,
        goal=args.goal,
        success_criteria=args.success_criteria,
        constraints=load_json_mapping(args.constraints),
        inputs=load_json_mapping(args.inputs),
    )
    run = await app.run_until_terminal(run.run_id, max_ticks=args.max_ticks)
    report = app.report(run.run_id)

    state_root = args.project_root / ".harness_state" / "runs" / run.run_id
    inbox_files = sorted((args.project_root / "shared_memory" / "inbox").glob("*.md"))
    correction_logs = sorted((args.project_root / "agents" / "watcher" / "corrections_log").glob("*.md"))

    return {
        "run_id": run.run_id,
        "status": run.status.value,
        "state_dir": str(state_root),
        "state_dir_exists": state_root.exists(),
        "inbox_files": [str(path) for path in inbox_files[-5:]],
        "correction_logs": [str(path) for path in correction_logs[-5:]],
        "report_summary": report.executive_summary,
    }


def main() -> None:
    args = build_parser().parse_args()
    payload = asyncio.run(run_smoke(args))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
