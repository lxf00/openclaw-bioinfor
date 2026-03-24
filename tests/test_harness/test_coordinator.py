from __future__ import annotations

from collections.abc import Iterable

import pytest

from bioopenclaw.harness.coordinator import HarnessCoordinator
from bioopenclaw.harness.models import (
    AgentInvocation,
    AgentResult,
    AgentResultStatus,
    ArtifactKind,
    ArtifactRef,
    TaskSpec,
)


class SequenceAgentGateway:
    def __init__(self, statuses: Iterable[AgentResultStatus]) -> None:
        self.statuses = list(statuses)
        self.invocations: list[AgentInvocation] = []

    async def invoke(self, invocation: AgentInvocation) -> AgentResult:
        self.invocations.append(invocation)
        status = self.statuses.pop(0) if self.statuses else AgentResultStatus.SUCCESS
        artifact = ArtifactRef(
            run_id=invocation.run_id,
            kind=ArtifactKind.REPORT,
            name=f"{invocation.target_agent}_summary",
            uri=f"memory://{invocation.target_agent}/{len(self.invocations)}",
            producer_agent=invocation.target_agent,
            stage_id=invocation.stage_id,
        )
        return AgentResult(
            invocation_id=invocation.invocation_id,
            status=status,
            summary=f"{invocation.target_agent} finished {invocation.stage_id}",
            artifacts=[artifact] if status == AgentResultStatus.SUCCESS else [],
        )


@pytest.mark.asyncio
async def test_coordinator_completes_default_plan() -> None:
    gateway = SequenceAgentGateway(
        [AgentResultStatus.SUCCESS] * 5,
    )
    coordinator = HarnessCoordinator(agent_gateway=gateway)
    run = coordinator.start_task(
        TaskSpec(
            title="Auto bioinformatics run",
            goal="Complete the default multi-agent workflow.",
            success_criteria=["result synthesis complete"],
        )
    )

    for _ in range(6):
        result = await coordinator.tick(run.run_id)

    assert result.run.status.value == "completed"
    assert len(result.state.completed_stages) == 5
    assert len(gateway.invocations) == 5


@pytest.mark.asyncio
async def test_governor_emits_proposal_after_repeated_failures() -> None:
    gateway = SequenceAgentGateway(
        [AgentResultStatus.FAILED, AgentResultStatus.FAILED],
    )
    coordinator = HarnessCoordinator(agent_gateway=gateway)
    run = coordinator.start_task(
        TaskSpec(
            title="Failure recovery run",
            goal="Observe governance on repeated failures.",
            success_criteria=["watcher proposal generated"],
        )
    )

    await coordinator.tick(run.run_id)
    result = await coordinator.tick(run.run_id)

    assert result.state.failure_count == 2
    assert result.governance.triggers
    assert result.governance.proposals
    assert result.governance.triggers[0].trigger_type.value == "excessive_retry"
