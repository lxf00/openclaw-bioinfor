from __future__ import annotations

import pytest

from bioopenclaw.harness.coordinator import HarnessCoordinator
from bioopenclaw.harness.file_store import FileHarnessStore
from bioopenclaw.harness.models import AgentInvocation, AgentResult, AgentResultStatus, TaskSpec


class SimpleSuccessGateway:
    async def invoke(self, invocation: AgentInvocation) -> AgentResult:
        return AgentResult(
            invocation_id=invocation.invocation_id,
            status=AgentResultStatus.SUCCESS,
            summary=f"{invocation.target_agent} completed {invocation.stage_id}",
            outputs={"success": True},
        )


@pytest.mark.asyncio
async def test_file_store_persists_run_state_and_steps(tmp_path) -> None:
    store = FileHarnessStore(tmp_path / "harness_state")
    coordinator = HarnessCoordinator(
        agent_gateway=SimpleSuccessGateway(),
        store=store,
    )
    run = coordinator.start_task(
        TaskSpec(
            title="Persistent run",
            goal="Persist harness state to disk.",
            success_criteria=["first stage completes"],
        )
    )

    await coordinator.tick(run.run_id)

    reloaded_store = FileHarnessStore(tmp_path / "harness_state")
    reloaded_run = reloaded_store.get_run(run.run_id)
    reloaded_state = reloaded_store.get_state(run.run_id)
    reloaded_steps = reloaded_store.list_steps(run.run_id)

    assert reloaded_run.task_id == run.task_id
    assert reloaded_state.completed_stages
    assert len(reloaded_steps) == 1
    assert reloaded_steps[0].summary
