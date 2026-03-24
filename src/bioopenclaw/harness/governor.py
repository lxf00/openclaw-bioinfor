"""Governance checks and correction proposals for harness runs."""

from __future__ import annotations

from bioopenclaw.harness.gateways import WatcherGateway
from bioopenclaw.harness.models import (
    CorrectionAction,
    CorrectionProposal,
    GovernanceOutcome,
    TaskRun,
    TaskState,
    TriggerSeverity,
    TriggerType,
    WatcherTrigger,
)
from bioopenclaw.harness.store import InMemoryHarnessStore


class Governor:
    """Evaluate execution health and persist watcher findings."""

    def __init__(self, store: InMemoryHarnessStore, watcher_gateway: WatcherGateway) -> None:
        self.store = store
        self.watcher_gateway = watcher_gateway

    async def evaluate(self, run: TaskRun, state: TaskState) -> GovernanceOutcome:
        recent_steps = self.store.list_steps(run.run_id)[-3:]
        recent_tool_calls = self.store.list_tool_calls(run.run_id)[-5:]
        repeated_failures = [step for step in recent_steps if step.status.value == "failed"]
        outcome = GovernanceOutcome()

        if len(repeated_failures) >= 2:
            trigger = WatcherTrigger(
                run_id=run.run_id,
                stage_id=repeated_failures[-1].stage_id,
                trigger_type=TriggerType.EXCESSIVE_RETRY,
                severity=TriggerSeverity.HIGH,
                evidence_refs=[step.step_id for step in repeated_failures],
                description="Two recent steps failed without progress.",
            )
            proposal = CorrectionProposal(
                run_id=run.run_id,
                trigger_id=trigger.trigger_id,
                action=CorrectionAction.REQUEST_VALIDATION,
                target_stage_id=trigger.stage_id,
                reason="Pause and inspect the failing stage before more retries.",
                confidence=0.8,
            )
            outcome.triggers.append(trigger)
            outcome.proposals.append(proposal)
            outcome.health = "risky"

        if any(count >= 3 for count in state.tool_call_counts.values()):
            trigger = WatcherTrigger(
                run_id=run.run_id,
                trigger_type=TriggerType.REPEATED_TOOL_CALL,
                severity=TriggerSeverity.MEDIUM,
                description="The same tool has been called repeatedly in this run.",
            )
            proposal = CorrectionProposal(
                run_id=run.run_id,
                trigger_id=trigger.trigger_id,
                action=CorrectionAction.NARROW_SCOPE,
                reason="Reduce scope before repeated tool execution continues.",
                confidence=0.7,
            )
            outcome.triggers.append(trigger)
            outcome.proposals.append(proposal)
            outcome.health = "risky"

        watcher_outcome = await self.watcher_gateway.assess(
            run.run_id,
            recent_tool_calls=recent_tool_calls,
            recent_outputs=[step.summary for step in recent_steps if step.summary],
        )
        if watcher_outcome.triggers or watcher_outcome.proposals:
            outcome.triggers.extend(watcher_outcome.triggers)
            outcome.proposals.extend(watcher_outcome.proposals)
            outcome.health = watcher_outcome.health or outcome.health

        for trigger in outcome.triggers:
            self.store.add_trigger(trigger)
        for proposal in outcome.proposals:
            self.store.add_proposal(proposal)

        return outcome
