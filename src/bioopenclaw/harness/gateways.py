"""Gateway interfaces for harness coordination."""

from __future__ import annotations

from typing import Protocol

from bioopenclaw.harness.models import (
    AgentInvocation,
    AgentResult,
    CorrectionProposal,
    GovernanceOutcome,
    Handoff,
    MemoryRecord,
    ToolCallRecord,
)


class AgentGateway(Protocol):
    """Invoke a specialist agent for a single harness step."""

    async def invoke(self, invocation: AgentInvocation) -> AgentResult:
        """Run a single agent invocation."""


class ToolGateway(Protocol):
    """Optional protocol-level tool execution surface."""

    async def record(self, call: ToolCallRecord) -> ToolCallRecord:
        """Persist or enrich tool execution details."""


class MemoryGateway(Protocol):
    """Persist task, agent, or shared memory entries."""

    async def write(self, record: MemoryRecord) -> MemoryRecord:
        """Write a memory record to the backing store."""


class InboxGateway(Protocol):
    """Persist explicit handoff messages between agents."""

    async def send(self, handoff: Handoff) -> Handoff:
        """Send a handoff to the inbox layer."""


class WatcherGateway(Protocol):
    """Evaluate recent execution history and suggest corrections."""

    async def assess(
        self,
        run_id: str,
        recent_tool_calls: list[ToolCallRecord],
        recent_outputs: list[str],
    ) -> GovernanceOutcome:
        """Return watcher findings for the current task run."""


class NullToolGateway:
    """No-op tool gateway for early harness bring-up."""

    async def record(self, call: ToolCallRecord) -> ToolCallRecord:
        return call


class NullMemoryGateway:
    """No-op memory gateway for tests or dry runs."""

    async def write(self, record: MemoryRecord) -> MemoryRecord:
        return record


class NullInboxGateway:
    """No-op inbox gateway for tests or dry runs."""

    async def send(self, handoff: Handoff) -> Handoff:
        return handoff


class NullWatcherGateway:
    """No-op watcher gateway for early harness bring-up."""

    async def assess(
        self,
        run_id: str,
        recent_tool_calls: list[ToolCallRecord],
        recent_outputs: list[str],
    ) -> GovernanceOutcome:
        return GovernanceOutcome()


class StaticWatcherGateway:
    """Watcher stub that always returns the provided proposals."""

    def __init__(self, outcome: GovernanceOutcome | None = None) -> None:
        self.outcome = outcome or GovernanceOutcome()

    async def assess(
        self,
        run_id: str,
        recent_tool_calls: list[ToolCallRecord],
        recent_outputs: list[str],
    ) -> GovernanceOutcome:
        return self.outcome
