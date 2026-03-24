"""Project-level harness application wiring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bioopenclaw.harness.adapters import ExistingServerAgentGateway, WatcherDetectorGateway
from bioopenclaw.harness.coordinator import HarnessCoordinator
from bioopenclaw.harness.file_store import FileHarnessStore
from bioopenclaw.harness.models import FinalReport, TaskPriority, TaskRun, TaskSpec, TickResult
from bioopenclaw.harness.state_surface import ProjectInboxGateway, ProjectStateSurface


class ProjectHarnessApp:
    """Convenience wrapper around a project-wired harness coordinator."""

    def __init__(self, coordinator: HarnessCoordinator) -> None:
        self.coordinator = coordinator

    @classmethod
    def from_project(
        cls,
        project_root: str | Path,
        *,
        state_root: str | Path | None = None,
        transport: str = "direct",
        tool_selection: dict[str, dict[str, Any]] | None = None,
        data_root: str | Path | None = None,
    ) -> "ProjectHarnessApp":
        project_root = Path(project_root)
        state_root = Path(state_root) if state_root else project_root / ".harness_state"
        store = FileHarnessStore(state_root)
        inbox_gateway = ProjectInboxGateway(project_root / "shared_memory" / "inbox")
        state_surface = ProjectStateSurface(
            store=store,
            agents_dir=project_root / "agents",
        )
        coordinator = HarnessCoordinator(
            agent_gateway=ExistingServerAgentGateway(
                tool_selection=tool_selection,
                transport=transport,
                repo_root=project_root,
                data_root=data_root or project_root,
            ),
            store=store,
            inbox_gateway=inbox_gateway,
            watcher_gateway=WatcherDetectorGateway(),
            state_surface=state_surface,
        )
        return cls(coordinator)

    def start_task(
        self,
        *,
        title: str,
        goal: str,
        success_criteria: list[str],
        priority: str = "medium",
        constraints: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        requested_by: str | None = None,
    ) -> TaskRun:
        task_spec = TaskSpec(
            title=title,
            goal=goal,
            success_criteria=success_criteria,
            priority=TaskPriority(priority),
            constraints=constraints or {},
            inputs=inputs or {},
            requested_by=requested_by,
        )
        return self.coordinator.start_task(task_spec)

    def resume_task(self, run_id: str) -> TaskRun:
        return self.coordinator.resume_task(run_id)

    async def tick(self, run_id: str) -> TickResult:
        return await self.coordinator.tick(run_id)

    async def run_until_terminal(self, run_id: str, *, max_ticks: int = 20) -> TaskRun:
        run = self.coordinator.resume_task(run_id)
        for _ in range(max_ticks):
            if run.status.value in {"completed", "failed", "cancelled"}:
                return run
            result = await self.coordinator.tick(run_id)
            run = result.run
        return run

    def report(self, run_id: str) -> FinalReport:
        return self.coordinator.reporter.build_final_report(run_id)


def load_json_mapping(path: str | Path | None) -> dict[str, Any] | None:
    """Load an optional JSON mapping file for tool selections or task inputs."""
    if path is None:
        return None
    payload = Path(path).read_text(encoding="utf-8")
    return json.loads(payload)
