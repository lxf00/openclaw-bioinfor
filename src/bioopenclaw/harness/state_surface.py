"""Projection of harness state into the repository's shared state files."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from bioopenclaw.harness.models import GovernanceOutcome, TaskRun, TaskState, WatcherEvent
from bioopenclaw.harness.store import InMemoryHarnessStore
from bioopenclaw.watcher.models import CorrectionRecord, Priority as WatcherPriority, TriggerType as WatcherTriggerType
from bioopenclaw.watcher.steering import SteeringQueue


class ProjectInboxGateway:
    """Write harness handoffs to the project's inbox directory."""

    def __init__(self, inbox_dir: str | Path) -> None:
        self.inbox_dir = Path(inbox_dir)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    async def send(self, handoff) -> object:
        created = handoff.created_at.strftime("%Y-%m-%dT%H-%M-%S")
        filename = f"{created}_{handoff.from_agent}_to_{handoff.to_agent}.md"
        path = self.inbox_dir / filename
        content = (
            f"---\n"
            f"from: {handoff.from_agent}\n"
            f"to: {handoff.to_agent}\n"
            f"priority: {handoff.priority.value}\n"
            f"created: {handoff.created_at.isoformat()}\n"
            f"type: handoff\n"
            f"task_id: {handoff.run_id}\n"
            f"stage: {handoff.stage_id}\n"
            f"---\n\n"
            f"# Harness Handoff\n\n"
            f"{handoff.intent}\n\n"
            f"Required outputs: {', '.join(handoff.required_outputs) or 'n/a'}\n"
        )
        path.write_text(content, encoding="utf-8")
        return handoff


class ProjectStateSurface:
    """Mirror harness execution into active_context and watcher logs."""

    HARNESS_START = "<!-- HARNESS:START -->"
    HARNESS_END = "<!-- HARNESS:END -->"

    def __init__(
        self,
        store: InMemoryHarnessStore,
        agents_dir: str | Path,
        steering_queue: SteeringQueue | None = None,
    ) -> None:
        self.store = store
        self.agents_dir = Path(agents_dir)
        self.steering_queue = steering_queue or SteeringQueue()

    def sync_run(self, run: TaskRun, state: TaskState) -> None:
        if run.current_agent:
            self._update_active_context(
                agent_name=run.current_agent,
                generated_lines=[
                    f"- Harness run: `{run.run_id}`",
                    f"- Current stage: `{run.current_stage_id or 'unknown'}`",
                    f"- Completed stages: {len(state.completed_stages)}",
                    f"- Failures: {state.failure_count}",
                ],
            )

        self._update_active_context(
            agent_name="watcher",
            generated_lines=[
                f"- Monitoring harness run `{run.run_id}`",
                f"- Current agent: `{run.current_agent or 'none'}`",
                f"- Open handoffs: {len(state.open_handoffs)}",
                f"- Known triggers: {len(self.store.list_triggers(run.run_id))}",
            ],
        )

    def emit_governance(self, run: TaskRun, governance: GovernanceOutcome) -> None:
        emitted_proposals = {
            event.proposal_id for event in self.store.list_events(run.run_id) if event.proposal_id
        }
        trigger_lookup = {trigger.trigger_id: trigger for trigger in governance.triggers}

        for proposal in governance.proposals:
            if proposal.proposal_id in emitted_proposals:
                continue

            trigger = trigger_lookup.get(proposal.trigger_id)
            target_agent = proposal.target_agent or run.current_agent or "research_agent"
            record = CorrectionRecord(
                target_agent=target_agent,
                trigger_type=_map_trigger_type(trigger.trigger_type.value if trigger else "repeated_tool_call"),
                trigger_details=trigger.description if trigger else proposal.reason,
                action=proposal.action.value,
                effect="pending",
                domain_tags=["harness", "governance"],
                priority=WatcherPriority.MEDIUM,
            )
            log_path = self.steering_queue.log_correction(record)
            self.steering_queue.write_inbox_message(
                target_agent=target_agent,
                message=(
                    f"[Harness {run.run_id}] {proposal.action.value}: "
                    f"{proposal.reason or 'See correction log for details.'}"
                ),
                priority="medium",
                trigger_type=(trigger.trigger_type.value if trigger else "repeated_tool_call"),
            )
            self.store.add_event(
                WatcherEvent(
                    run_id=run.run_id,
                    trigger_id=proposal.trigger_id,
                    proposal_id=proposal.proposal_id,
                    applied_action="watcher_logged_and_queued",
                    outcome=str(log_path),
                )
            )

    def _update_active_context(self, agent_name: str, generated_lines: list[str]) -> None:
        path = self.agents_dir / agent_name / "active_context.md"
        if not path.exists():
            return

        content = path.read_text(encoding="utf-8")
        block = (
            f"{self.HARNESS_START}\n"
            f"{chr(10).join(generated_lines)}\n"
            f"{self.HARNESS_END}\n"
        )

        if self.HARNESS_START in content and self.HARNESS_END in content:
            content = re.sub(
                rf"{re.escape(self.HARNESS_START)}.*?{re.escape(self.HARNESS_END)}\n?",
                block,
                content,
                flags=re.DOTALL,
            )
        elif "## Current Focus" in content:
            content = content.replace("## Current Focus\n", f"## Current Focus\n{block}")
        else:
            content += f"\n## Current Focus\n{block}"

        content = re.sub(
            r"^---\nlast_session:.*?\n---",
            f"---\nlast_session: {datetime.utcnow().isoformat()}\n---",
            content,
            flags=re.DOTALL,
        )
        path.write_text(content, encoding="utf-8")


def _map_trigger_type(trigger_type: str) -> WatcherTriggerType:
    mapping = {
        "repeated_tool_call": WatcherTriggerType.REPEATED_TOOL_CALL,
        "no_progress": WatcherTriggerType.OUTPUT_STAGNATION,
        "excessive_retry": WatcherTriggerType.MAX_ROUNDS_EXCEEDED,
    }
    return mapping.get(trigger_type, WatcherTriggerType.REPEATED_TOOL_CALL)
