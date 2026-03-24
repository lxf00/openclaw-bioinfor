"""State persistence primitives for the harness."""

from __future__ import annotations

from typing import Protocol

from bioopenclaw.harness.models import (
    AgentResult,
    ArtifactRef,
    CorrectionProposal,
    ExecutionPlan,
    FinalReport,
    Handoff,
    MemoryRecord,
    StepRecord,
    TaskRun,
    TaskSpec,
    TaskState,
    ToolCallRecord,
    WatcherEvent,
    WatcherTrigger,
)


class HarnessStore(Protocol):
    """Storage contract for harness state and artifacts."""

    def save_task_spec(self, spec: TaskSpec) -> None:
        """Persist a task definition."""

    def get_task_spec(self, task_id: str) -> TaskSpec:
        """Load a task definition."""

    def save_plan(self, plan: ExecutionPlan) -> None:
        """Persist an execution plan."""

    def get_plan(self, plan_id: str) -> ExecutionPlan:
        """Load an execution plan."""

    def save_run(self, run: TaskRun) -> None:
        """Persist a run record."""

    def get_run(self, run_id: str) -> TaskRun:
        """Load a run record."""

    def save_state(self, state: TaskState) -> None:
        """Persist run state."""

    def get_state(self, run_id: str) -> TaskState:
        """Load run state."""


class InMemoryHarnessStore:
    """Simple store suitable for tests and local bring-up."""

    def __init__(self) -> None:
        self.task_specs: dict[str, TaskSpec] = {}
        self.plans: dict[str, ExecutionPlan] = {}
        self.runs: dict[str, TaskRun] = {}
        self.states: dict[str, TaskState] = {}
        self.steps: dict[str, list[StepRecord]] = {}
        self.agent_results: dict[str, AgentResult] = {}
        self.artifacts: dict[str, ArtifactRef] = {}
        self.handoffs: dict[str, Handoff] = {}
        self.memories: dict[str, MemoryRecord] = {}
        self.tool_calls: dict[str, ToolCallRecord] = {}
        self.triggers: dict[str, WatcherTrigger] = {}
        self.proposals: dict[str, CorrectionProposal] = {}
        self.events: dict[str, WatcherEvent] = {}
        self.reports: dict[str, FinalReport] = {}

    def save_task_spec(self, spec: TaskSpec) -> None:
        self.task_specs[spec.task_id] = spec

    def get_task_spec(self, task_id: str) -> TaskSpec:
        return self.task_specs[task_id]

    def save_plan(self, plan: ExecutionPlan) -> None:
        self.plans[plan.plan_id] = plan

    def get_plan(self, plan_id: str) -> ExecutionPlan:
        return self.plans[plan_id]

    def save_run(self, run: TaskRun) -> None:
        self.runs[run.run_id] = run

    def get_run(self, run_id: str) -> TaskRun:
        return self.runs[run_id]

    def save_state(self, state: TaskState) -> None:
        self.states[state.run_id] = state

    def get_state(self, run_id: str) -> TaskState:
        return self.states[run_id]

    def add_step(self, step: StepRecord) -> None:
        self.steps.setdefault(step.run_id, []).append(step)

    def list_steps(self, run_id: str) -> list[StepRecord]:
        return list(self.steps.get(run_id, []))

    def save_agent_result(self, result: AgentResult) -> None:
        self.agent_results[result.invocation_id] = result

    def add_artifact(self, artifact: ArtifactRef) -> None:
        self.artifacts[artifact.artifact_id] = artifact

    def list_artifacts(self, run_id: str) -> list[ArtifactRef]:
        return [artifact for artifact in self.artifacts.values() if artifact.run_id == run_id]

    def add_handoff(self, handoff: Handoff) -> None:
        self.handoffs[handoff.handoff_id] = handoff

    def list_handoffs(self, run_id: str, only_open: bool = False) -> list[Handoff]:
        handoffs = [handoff for handoff in self.handoffs.values() if handoff.run_id == run_id]
        if only_open:
            handoffs = [handoff for handoff in handoffs if handoff.status.value == "open"]
        return handoffs

    def add_memory(self, record: MemoryRecord) -> None:
        self.memories[record.memory_id] = record

    def add_tool_call(self, call: ToolCallRecord) -> None:
        self.tool_calls[call.tool_call_id] = call

    def list_tool_calls(self, run_id: str) -> list[ToolCallRecord]:
        return [call for call in self.tool_calls.values() if call.run_id == run_id]

    def add_trigger(self, trigger: WatcherTrigger) -> None:
        self.triggers[trigger.trigger_id] = trigger

    def list_triggers(self, run_id: str) -> list[WatcherTrigger]:
        return [trigger for trigger in self.triggers.values() if trigger.run_id == run_id]

    def add_proposal(self, proposal: CorrectionProposal) -> None:
        self.proposals[proposal.proposal_id] = proposal

    def list_proposals(self, run_id: str) -> list[CorrectionProposal]:
        return [proposal for proposal in self.proposals.values() if proposal.run_id == run_id]

    def add_event(self, event: WatcherEvent) -> None:
        self.events[event.event_id] = event

    def list_events(self, run_id: str) -> list[WatcherEvent]:
        return [event for event in self.events.values() if event.run_id == run_id]

    def save_report(self, report: FinalReport) -> None:
        self.reports[report.run_id] = report

    def get_report(self, run_id: str) -> FinalReport | None:
        return self.reports.get(run_id)
