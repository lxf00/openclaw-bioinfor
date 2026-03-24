"""Snapshot and report builders for harness runs."""

from __future__ import annotations

from bioopenclaw.harness.models import FinalReport, RunStatus, TaskRun, TaskSnapshot
from bioopenclaw.harness.store import InMemoryHarnessStore


class Reporter:
    """Produce concise snapshots and final reports."""

    def __init__(self, store: InMemoryHarnessStore) -> None:
        self.store = store

    def snapshot(self, run_id: str) -> TaskSnapshot:
        run = self.store.get_run(run_id)
        state = self.store.get_state(run_id)
        return TaskSnapshot(
            run=run,
            state=state,
            recent_steps=self.store.list_steps(run_id)[-5:],
            open_handoffs=self.store.list_handoffs(run_id, only_open=True),
            recent_triggers=self.store.list_triggers(run_id)[-5:],
        )

    def build_final_report(self, run_id: str) -> FinalReport:
        run = self.store.get_run(run_id)
        spec = self.store.get_task_spec(run.task_id)
        triggers = self.store.list_triggers(run_id)
        artifacts = self.store.list_artifacts(run_id)
        steps = self.store.list_steps(run_id)

        report = FinalReport(
            run_id=run.run_id,
            task_id=run.task_id,
            status=run.status,
            executive_summary=steps[-1].summary if steps else spec.goal,
            key_findings=[step.summary for step in steps if step.summary][-3:],
            artifact_refs=[artifact.artifact_id for artifact in artifacts],
            unresolved_risks=[trigger.description for trigger in triggers if trigger.description],
            watcher_summary=[trigger.trigger_type.value for trigger in triggers],
        )
        self.store.save_report(report)
        return report

    def mark_completed(self, run: TaskRun) -> TaskRun:
        run.status = RunStatus.COMPLETED
        self.store.save_run(run)
        return run
