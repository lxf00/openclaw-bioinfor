"""File-backed harness store for persistent task execution state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

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
from bioopenclaw.harness.store import InMemoryHarnessStore

ModelT = TypeVar("ModelT", bound=BaseModel)


class FileHarnessStore(InMemoryHarnessStore):
    """Persist harness objects to a JSON-backed directory tree."""

    def __init__(self, root_dir: str | Path) -> None:
        super().__init__()
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_task_spec(self, spec: TaskSpec) -> None:
        super().save_task_spec(spec)
        self._write_model(self.root_dir / "tasks" / spec.task_id / "spec.json", spec)

    def get_task_spec(self, task_id: str) -> TaskSpec:
        if task_id not in self.task_specs:
            path = self.root_dir / "tasks" / task_id / "spec.json"
            self.task_specs[task_id] = self._read_model(path, TaskSpec)
        return super().get_task_spec(task_id)

    def save_plan(self, plan: ExecutionPlan) -> None:
        super().save_plan(plan)
        self._write_model(self.root_dir / "plans" / plan.plan_id / "plan.json", plan)

    def get_plan(self, plan_id: str) -> ExecutionPlan:
        if plan_id not in self.plans:
            path = self.root_dir / "plans" / plan_id / "plan.json"
            self.plans[plan_id] = self._read_model(path, ExecutionPlan)
        return super().get_plan(plan_id)

    def save_run(self, run: TaskRun) -> None:
        super().save_run(run)
        self._write_model(self.root_dir / "runs" / run.run_id / "run.json", run)

    def get_run(self, run_id: str) -> TaskRun:
        if run_id not in self.runs:
            path = self.root_dir / "runs" / run_id / "run.json"
            self.runs[run_id] = self._read_model(path, TaskRun)
        return super().get_run(run_id)

    def save_state(self, state: TaskState) -> None:
        super().save_state(state)
        self._write_model(self.root_dir / "runs" / state.run_id / "state.json", state)

    def get_state(self, run_id: str) -> TaskState:
        if run_id not in self.states:
            path = self.root_dir / "runs" / run_id / "state.json"
            self.states[run_id] = self._read_model(path, TaskState)
        return super().get_state(run_id)

    def add_step(self, step: StepRecord) -> None:
        super().add_step(step)
        self._write_model(self.root_dir / "runs" / step.run_id / "steps" / f"{step.step_id}.json", step)

    def list_steps(self, run_id: str) -> list[StepRecord]:
        if run_id not in self.steps:
            self.steps[run_id] = self._read_collection(
                self.root_dir / "runs" / run_id / "steps",
                StepRecord,
            )
        return super().list_steps(run_id)

    def save_agent_result(self, result: AgentResult) -> None:
        super().save_agent_result(result)
        self._write_model(
            self.root_dir / "results" / f"{result.invocation_id}.json",
            result,
        )

    def add_artifact(self, artifact: ArtifactRef) -> None:
        super().add_artifact(artifact)
        self._write_model(
            self.root_dir / "runs" / artifact.run_id / "artifacts" / f"{artifact.artifact_id}.json",
            artifact,
        )

    def list_artifacts(self, run_id: str) -> list[ArtifactRef]:
        artifacts = self._read_collection(self.root_dir / "runs" / run_id / "artifacts", ArtifactRef)
        if artifacts:
            for artifact in artifacts:
                self.artifacts[artifact.artifact_id] = artifact
            return artifacts
        return super().list_artifacts(run_id)

    def add_handoff(self, handoff: Handoff) -> None:
        super().add_handoff(handoff)
        self._write_model(
            self.root_dir / "runs" / handoff.run_id / "handoffs" / f"{handoff.handoff_id}.json",
            handoff,
        )

    def list_handoffs(self, run_id: str, only_open: bool = False) -> list[Handoff]:
        handoffs = self._read_collection(self.root_dir / "runs" / run_id / "handoffs", Handoff)
        if handoffs:
            for handoff in handoffs:
                self.handoffs[handoff.handoff_id] = handoff
        return super().list_handoffs(run_id, only_open=only_open)

    def add_memory(self, record: MemoryRecord) -> None:
        super().add_memory(record)
        self._write_model(
            self.root_dir / "runs" / record.run_id / "memories" / f"{record.memory_id}.json",
            record,
        )

    def add_tool_call(self, call: ToolCallRecord) -> None:
        super().add_tool_call(call)
        self._write_model(
            self.root_dir / "runs" / call.run_id / "tool_calls" / f"{call.tool_call_id}.json",
            call,
        )

    def list_tool_calls(self, run_id: str) -> list[ToolCallRecord]:
        calls = self._read_collection(self.root_dir / "runs" / run_id / "tool_calls", ToolCallRecord)
        if calls:
            for call in calls:
                self.tool_calls[call.tool_call_id] = call
            return calls
        return super().list_tool_calls(run_id)

    def add_trigger(self, trigger: WatcherTrigger) -> None:
        super().add_trigger(trigger)
        self._write_model(
            self.root_dir / "runs" / trigger.run_id / "triggers" / f"{trigger.trigger_id}.json",
            trigger,
        )

    def list_triggers(self, run_id: str) -> list[WatcherTrigger]:
        triggers = self._read_collection(self.root_dir / "runs" / run_id / "triggers", WatcherTrigger)
        if triggers:
            for trigger in triggers:
                self.triggers[trigger.trigger_id] = trigger
        return super().list_triggers(run_id)

    def add_proposal(self, proposal: CorrectionProposal) -> None:
        super().add_proposal(proposal)
        self._write_model(
            self.root_dir / "runs" / proposal.run_id / "proposals" / f"{proposal.proposal_id}.json",
            proposal,
        )

    def list_proposals(self, run_id: str) -> list[CorrectionProposal]:
        proposals = self._read_collection(
            self.root_dir / "runs" / run_id / "proposals",
            CorrectionProposal,
        )
        if proposals:
            for proposal in proposals:
                self.proposals[proposal.proposal_id] = proposal
        return super().list_proposals(run_id)

    def add_event(self, event: WatcherEvent) -> None:
        super().add_event(event)
        self._write_model(
            self.root_dir / "runs" / event.run_id / "events" / f"{event.event_id}.json",
            event,
        )

    def list_events(self, run_id: str) -> list[WatcherEvent]:
        events = self._read_collection(self.root_dir / "runs" / run_id / "events", WatcherEvent)
        if events:
            for event in events:
                self.events[event.event_id] = event
        return super().list_events(run_id)

    def save_report(self, report: FinalReport) -> None:
        super().save_report(report)
        self._write_model(
            self.root_dir / "runs" / report.run_id / "final_report.json",
            report,
        )

    def get_report(self, run_id: str) -> FinalReport | None:
        report = super().get_report(run_id)
        if report is not None:
            return report

        path = self.root_dir / "runs" / run_id / "final_report.json"
        if path.exists():
            report = self._read_model(path, FinalReport)
            self.reports[run_id] = report
            return report
        return None

    def _write_model(self, path: Path, model: BaseModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(model.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _read_model(self, path: Path, model_type: type[ModelT]) -> ModelT:
        data = json.loads(path.read_text(encoding="utf-8"))
        return model_type.model_validate(data)

    def _read_collection(self, path: Path, model_type: type[ModelT]) -> list[ModelT]:
        if not path.exists():
            return []
        items: list[ModelT] = []
        for item_path in sorted(path.glob("*.json")):
            items.append(self._read_model(item_path, model_type))
        return items
