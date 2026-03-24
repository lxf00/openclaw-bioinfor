from __future__ import annotations

from pathlib import Path

import pytest

from bioopenclaw.harness.coordinator import HarnessCoordinator
from bioopenclaw.harness.file_store import FileHarnessStore
from bioopenclaw.harness.models import (
    AgentInvocation,
    AgentResult,
    AgentResultStatus,
    Handoff,
    TaskSpec,
)
from bioopenclaw.harness.state_surface import ProjectInboxGateway, ProjectStateSurface
from bioopenclaw.watcher import steering as steering_module


ACTIVE_CONTEXT_TEMPLATE = """---
last_session: 2026-03-21T00:00:00
---

# Active Context

## Current Focus
（暂无）

## Blocked
（暂无）

## Next Steps
（暂无）

## Recent Decisions
（暂无）
"""


class FailingGateway:
    async def invoke(self, invocation: AgentInvocation) -> AgentResult:
        return AgentResult(
            invocation_id=invocation.invocation_id,
            status=AgentResultStatus.FAILED,
            summary="Repeated failure for governance projection.",
            outputs={"success": False, "error": "forced failure"},
        )


@pytest.mark.asyncio
async def test_project_inbox_gateway_writes_markdown_handoff(tmp_path: Path) -> None:
    inbox = tmp_path / "shared_memory" / "inbox"
    gateway = ProjectInboxGateway(inbox)
    handoff = Handoff(
        run_id="run_123",
        from_agent="research_agent",
        to_agent="data_agent",
        stage_id="stage_data",
        intent="Prepare a filtered dataset for downstream analysis.",
        required_outputs=["qc_dataset"],
    )

    await gateway.send(handoff)

    files = list(inbox.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "from: research_agent" in content
    assert "to: data_agent" in content
    assert "Harness Handoff" in content


@pytest.mark.asyncio
async def test_project_state_surface_updates_context_and_watcher_log(tmp_path: Path, monkeypatch) -> None:
    agents_dir = tmp_path / "agents"
    inbox_dir = tmp_path / "shared_memory" / "inbox"
    corrections_dir = agents_dir / "watcher" / "corrections_log"
    for agent in ["scout_agent", "watcher"]:
        agent_dir = agents_dir / agent
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "active_context.md").write_text(ACTIVE_CONTEXT_TEMPLATE, encoding="utf-8")

    _Cfg = type(
        "_Cfg",
        (),
        {
            "corrections_log_dir": str(corrections_dir),
            "inbox_dir": str(inbox_dir),
        },
    )

    original_get_config = steering_module.get_config
    monkeypatch.setattr(steering_module, "get_config", lambda: _Cfg())

    try:
        store = FileHarnessStore(tmp_path / "harness_state")
        surface = ProjectStateSurface(store=store, agents_dir=agents_dir)
        coordinator = HarnessCoordinator(
            agent_gateway=FailingGateway(),
            store=store,
            state_surface=surface,
        )
        run = coordinator.start_task(
            TaskSpec(
                title="Governance projection run",
                goal="Project harness state to external files.",
                success_criteria=["watcher log written"],
            )
        )

        await coordinator.tick(run.run_id)
        await coordinator.tick(run.run_id)
    finally:
        monkeypatch.setattr(steering_module, "get_config", original_get_config)

    scout_context = (agents_dir / "scout_agent" / "active_context.md").read_text(encoding="utf-8")
    watcher_context = (agents_dir / "watcher" / "active_context.md").read_text(encoding="utf-8")

    assert "<!-- HARNESS:START -->" in scout_context
    assert "Harness run:" in scout_context
    assert "Monitoring harness run" in watcher_context

    correction_logs = list(corrections_dir.glob("*.md"))
    watcher_messages = list(inbox_dir.glob("*.md"))
    assert correction_logs
    assert watcher_messages
