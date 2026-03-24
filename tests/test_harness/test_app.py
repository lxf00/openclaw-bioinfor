from __future__ import annotations

from pathlib import Path

import pytest

from bioopenclaw.harness.app import ProjectHarnessApp
from bioopenclaw.harness.coordinator import HarnessCoordinator
from bioopenclaw.harness.file_store import FileHarnessStore
from bioopenclaw.harness.models import AgentInvocation, AgentResult, AgentResultStatus


class SuccessGateway:
    async def invoke(self, invocation: AgentInvocation) -> AgentResult:
        return AgentResult(
            invocation_id=invocation.invocation_id,
            status=AgentResultStatus.SUCCESS,
            summary=f"{invocation.target_agent} finished {invocation.stage_id}",
            outputs={"success": True},
        )


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
async def test_project_harness_app_run_and_report(tmp_path: Path) -> None:
    for agent in ["scout_agent", "research_agent", "data_agent", "model_agent", "watcher"]:
        _write_active_context(tmp_path / "agents" / agent / "active_context.md")

    store = FileHarnessStore(tmp_path / ".harness_state")
    app = ProjectHarnessApp(
        HarnessCoordinator(
            agent_gateway=SuccessGateway(),
            store=store,
        )
    )

    run = app.start_task(
        title="CLI-like harness run",
        goal="Complete the default plan successfully.",
        success_criteria=["all stages completed"],
    )
    final_run = await app.run_until_terminal(run.run_id, max_ticks=10)
    report = app.report(run.run_id)

    assert final_run.status.value == "completed"
    assert report.run_id == run.run_id
    assert report.status.value == "completed"
    assert report.key_findings
