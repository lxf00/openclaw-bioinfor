"""Top-level harness coordinator."""

from __future__ import annotations

from datetime import datetime

from bioopenclaw.harness.gateways import (
    AgentGateway,
    InboxGateway,
    MemoryGateway,
    NullInboxGateway,
    NullMemoryGateway,
    NullToolGateway,
    NullWatcherGateway,
    ToolGateway,
    WatcherGateway,
)
from bioopenclaw.harness.governor import Governor
from bioopenclaw.harness.models import DecisionType, RunStatus, TaskRun, TaskSpec, TaskState, TickResult
from bioopenclaw.harness.planner import DefaultPlanner
from bioopenclaw.harness.reporter import Reporter
from bioopenclaw.harness.runtime import Runtime
from bioopenclaw.harness.scheduler import DefaultScheduler
from bioopenclaw.harness.state_surface import ProjectStateSurface
from bioopenclaw.harness.store import InMemoryHarnessStore


class HarnessCoordinator:
    """Own task lifecycle, tick execution, and governance checks."""

    def __init__(
        self,
        agent_gateway: AgentGateway,
        store: InMemoryHarnessStore | None = None,
        planner: DefaultPlanner | None = None,
        scheduler: DefaultScheduler | None = None,
        tool_gateway: ToolGateway | None = None,
        memory_gateway: MemoryGateway | None = None,
        inbox_gateway: InboxGateway | None = None,
        watcher_gateway: WatcherGateway | None = None,
        state_surface: ProjectStateSurface | None = None,
    ) -> None:
        self.store = store or InMemoryHarnessStore()
        self.planner = planner or DefaultPlanner()
        self.scheduler = scheduler or DefaultScheduler()
        self.runtime = Runtime(
            store=self.store,
            agent_gateway=agent_gateway,
            tool_gateway=tool_gateway or NullToolGateway(),
            memory_gateway=memory_gateway or NullMemoryGateway(),
            inbox_gateway=inbox_gateway or NullInboxGateway(),
        )
        self.governor = Governor(self.store, watcher_gateway or NullWatcherGateway())
        self.reporter = Reporter(self.store)
        self.state_surface = state_surface

    def start_task(self, task_spec: TaskSpec) -> TaskRun:
        plan = self.planner.build_plan(task_spec)
        run = TaskRun(
            task_id=task_spec.task_id,
            plan_id=plan.plan_id,
            status=RunStatus.RUNNING,
        )
        state = TaskState(run_id=run.run_id)
        self.store.save_task_spec(task_spec)
        self.store.save_plan(plan)
        self.store.save_run(run)
        self.store.save_state(state)
        if self.state_surface is not None:
            self.state_surface.sync_run(run, state)
        return run

    def resume_task(self, run_id: str) -> TaskRun:
        return self.store.get_run(run_id)

    async def tick(self, run_id: str) -> TickResult:
        run = self.store.get_run(run_id)
        state = self.store.get_state(run_id)
        plan = self.store.get_plan(run.plan_id)

        decision = self.scheduler.decide(run, state, plan)
        run.updated_at = datetime.utcnow()

        if decision.decision_type == DecisionType.MARK_COMPLETED:
            run.status = RunStatus.COMPLETED
            run.finished_at = datetime.utcnow()
            self.store.save_run(run)
            self.store.save_state(state)
            governance = await self.governor.evaluate(run, state)
            if self.state_surface is not None:
                self.state_surface.sync_run(run, state)
                self.state_surface.emit_governance(run, governance)
            return TickResult(run=run, state=state, decision=decision, governance=governance)

        if decision.decision_type == DecisionType.TERMINATE_RUN:
            run.status = RunStatus.FAILED
            run.finished_at = datetime.utcnow()
            self.store.save_run(run)
            self.store.save_state(state)
            governance = await self.governor.evaluate(run, state)
            if self.state_surface is not None:
                self.state_surface.sync_run(run, state)
                self.state_surface.emit_governance(run, governance)
            return TickResult(run=run, state=state, decision=decision, governance=governance)

        if decision.stage_id not in state.active_stages:
            state.active_stages.append(decision.stage_id)

        run.current_stage_id = decision.stage_id
        run.current_agent = decision.target_agent
        self.store.save_run(run)

        step = await self.runtime.execute(run, state, plan, decision)
        governance = await self.governor.evaluate(run, state)

        if state.failure_count >= self.store.get_task_spec(run.task_id).budget.max_total_failures:
            run.status = RunStatus.FAILED
            run.finished_at = datetime.utcnow()

        self.store.save_run(run)
        self.store.save_state(state)
        if self.state_surface is not None:
            self.state_surface.sync_run(run, state)
            self.state_surface.emit_governance(run, governance)
        return TickResult(run=run, state=state, decision=decision, step=step, governance=governance)
