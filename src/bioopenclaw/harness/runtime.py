"""Execution runtime for harness decisions."""

from __future__ import annotations

from datetime import datetime

from bioopenclaw.harness.gateways import AgentGateway, InboxGateway, MemoryGateway, ToolGateway
from bioopenclaw.harness.models import (
    AgentInvocation,
    AgentResult,
    AgentResultStatus,
    DecisionType,
    ExecutionDecision,
    ExecutionPlan,
    StepRecord,
    StepStatus,
    TaskRun,
    TaskState,
)
from bioopenclaw.harness.store import InMemoryHarnessStore


class Runtime:
    """Execute a single scheduler decision."""

    def __init__(
        self,
        store: InMemoryHarnessStore,
        agent_gateway: AgentGateway,
        tool_gateway: ToolGateway,
        memory_gateway: MemoryGateway,
        inbox_gateway: InboxGateway,
    ) -> None:
        self.store = store
        self.agent_gateway = agent_gateway
        self.tool_gateway = tool_gateway
        self.memory_gateway = memory_gateway
        self.inbox_gateway = inbox_gateway

    async def execute(
        self,
        run: TaskRun,
        state: TaskState,
        plan: ExecutionPlan,
        decision: ExecutionDecision,
    ) -> StepRecord | None:
        if decision.decision_type != DecisionType.INVOKE_AGENT or not decision.target_agent:
            return None

        stage = next(stage for stage in plan.stages if stage.stage_id == decision.stage_id)
        invocation = AgentInvocation(
            run_id=run.run_id,
            stage_id=stage.stage_id,
            target_agent=decision.target_agent,
            objective=decision.intent or stage.description,
            context_refs=list(state.artifacts),
            required_outputs=stage.expected_outputs,
            constraints=decision.required_inputs,
        )
        result = await self.agent_gateway.invoke(invocation)
        step = StepRecord(
            run_id=run.run_id,
            stage_id=stage.stage_id,
            agent=decision.target_agent,
            decision_id=decision.decision_id,
            status=self._map_status(result.status),
            finished_at=datetime.utcnow(),
            summary=result.summary,
            produced_artifacts=[artifact.artifact_id for artifact in result.artifacts],
            invocation_id=invocation.invocation_id,
        )

        self.store.add_step(step)
        self.store.save_agent_result(result)

        for artifact in result.artifacts:
            self.store.add_artifact(artifact)

        for handoff in result.proposed_handoffs:
            await self.inbox_gateway.send(handoff)
            self.store.add_handoff(handoff)

        for memory in result.memories:
            await self.memory_gateway.write(memory)
            self.store.add_memory(memory)

        for tool_call in result.tool_calls:
            await self.tool_gateway.record(tool_call)
            self.store.add_tool_call(tool_call)

        self._apply_result_to_state(state, step, result)
        return step

    def _apply_result_to_state(
        self,
        state: TaskState,
        step: StepRecord,
        result: AgentResult,
    ) -> None:
        stage_id = step.stage_id

        if stage_id in state.active_stages:
            state.active_stages.remove(stage_id)

        if result.status == AgentResultStatus.SUCCESS:
            if stage_id not in state.completed_stages:
                state.completed_stages.append(stage_id)
            if stage_id in state.failed_stages:
                state.failed_stages.remove(stage_id)
            state.last_progress_at = datetime.utcnow()
        elif result.status == AgentResultStatus.BLOCKED:
            if stage_id not in state.blocked_stages:
                state.blocked_stages.append(stage_id)
        else:
            if stage_id not in state.failed_stages:
                state.failed_stages.append(stage_id)
            state.retry_counts[stage_id] = state.retry_counts.get(stage_id, 0) + 1
            state.failure_count += 1

        for artifact in result.artifacts:
            if artifact.artifact_id not in state.artifacts:
                state.artifacts.append(artifact.artifact_id)

        for handoff in result.proposed_handoffs:
            if handoff.handoff_id not in state.open_handoffs:
                state.open_handoffs.append(handoff.handoff_id)

        for tool_call in result.tool_calls:
            key = f"{tool_call.agent}:{tool_call.tool_name}"
            state.tool_call_counts[key] = state.tool_call_counts.get(key, 0) + 1

    @staticmethod
    def _map_status(result_status: AgentResultStatus) -> StepStatus:
        mapping = {
            AgentResultStatus.SUCCESS: StepStatus.SUCCESS,
            AgentResultStatus.FAILED: StepStatus.FAILED,
            AgentResultStatus.BLOCKED: StepStatus.BLOCKED,
            AgentResultStatus.NEEDS_REVIEW: StepStatus.BLOCKED,
        }
        return mapping[result_status]
