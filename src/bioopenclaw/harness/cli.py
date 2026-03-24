"""Command-line entrypoint for the BioOpenClaw harness."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from bioopenclaw.harness.app import ProjectHarnessApp, load_json_mapping


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BioOpenClaw harness task runner")
    parser.add_argument("--project-root", default=".", help="Repository root for project-backed state")
    parser.add_argument("--state-root", default=None, help="Override persistent harness state directory")
    parser.add_argument(
        "--transport",
        choices=["direct", "stdio"],
        default="direct",
        help="Agent invocation transport",
    )
    parser.add_argument(
        "--tool-map",
        default=None,
        help="Optional JSON file mapping agent names to tool_name/tool_args",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Create a new harness task")
    start.add_argument("--title", required=True)
    start.add_argument("--goal", required=True)
    start.add_argument(
        "--success-criterion",
        action="append",
        dest="success_criteria",
        required=True,
        help="Repeatable success criterion",
    )
    start.add_argument("--priority", default="medium", choices=["low", "medium", "high", "critical"])
    start.add_argument("--constraints", default=None, help="Optional JSON file for task constraints")
    start.add_argument("--inputs", default=None, help="Optional JSON file for task inputs")
    start.add_argument("--requested-by", default=None)
    start.add_argument("--auto-run", action="store_true", help="Tick until terminal status")
    start.add_argument("--max-ticks", type=int, default=20)

    tick = subparsers.add_parser("tick", help="Advance a run by one scheduler step")
    tick.add_argument("--run-id", required=True)

    run = subparsers.add_parser("run", help="Tick a run until completion or max ticks")
    run.add_argument("--run-id", required=True)
    run.add_argument("--max-ticks", type=int, default=20)

    report = subparsers.add_parser("report", help="Build a final report for a run")
    report.add_argument("--run-id", required=True)
    return parser


async def run_cli(args: argparse.Namespace) -> dict[str, Any]:
    app = ProjectHarnessApp.from_project(
        project_root=Path(args.project_root),
        state_root=Path(args.state_root) if args.state_root else None,
        transport=args.transport,
        tool_selection=load_json_mapping(args.tool_map),
    )

    if args.command == "start":
        run = app.start_task(
            title=args.title,
            goal=args.goal,
            success_criteria=args.success_criteria,
            priority=args.priority,
            constraints=load_json_mapping(args.constraints),
            inputs=load_json_mapping(args.inputs),
            requested_by=args.requested_by,
        )
        if args.auto_run:
            run = await app.run_until_terminal(run.run_id, max_ticks=args.max_ticks)
        return {"run_id": run.run_id, "task_id": run.task_id, "status": run.status.value}

    if args.command == "tick":
        result = await app.tick(args.run_id)
        return {
            "run_id": result.run.run_id,
            "status": result.run.status.value,
            "decision": result.decision.decision_type.value,
            "health": result.governance.health,
        }

    if args.command == "run":
        run = await app.run_until_terminal(args.run_id, max_ticks=args.max_ticks)
        return {"run_id": run.run_id, "status": run.status.value}

    if args.command == "report":
        report = app.report(args.run_id)
        return report.model_dump(mode="json")

    raise ValueError(f"Unsupported command: {args.command}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    payload = asyncio.run(run_cli(args))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
