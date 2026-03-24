"""Decision logic for the next harness step."""

from __future__ import annotations

from bioopenclaw.harness.models import DecisionType, ExecutionDecision, ExecutionPlan, TaskRun, TaskState


class DefaultScheduler:
    """Select the next actionable stage in dependency order."""

    def decide(self, run: TaskRun, state: TaskState, plan: ExecutionPlan) -> ExecutionDecision:
        completed = set(state.completed_stages)
        blocked = set(state.blocked_stages)
        failed = set(state.failed_stages)

        for stage in plan.stages:
            if stage.stage_id in completed or stage.stage_id in blocked:
                continue

            if any(dep not in completed for dep in stage.depends_on):
                continue

            retries = state.retry_counts.get(stage.stage_id, 0)
            if stage.stage_id in failed and retries >= stage.retry_limit:
                return ExecutionDecision(
                    run_id=run.run_id,
                    stage_id=stage.stage_id,
                    decision_type=DecisionType.TERMINATE_RUN,
                    target_agent=stage.owner_agent,
                    reason=f"Retry limit reached for stage '{stage.name}'.",
                )

            return ExecutionDecision(
                run_id=run.run_id,
                stage_id=stage.stage_id,
                decision_type=DecisionType.INVOKE_AGENT,
                target_agent=stage.owner_agent,
                intent=stage.description,
                required_inputs={
                    "expected_outputs": stage.expected_outputs,
                    "tool_name": stage.tool_name,
                    "tool_args": dict(stage.tool_args),
                    "stage_metadata": dict(stage.metadata),
                },
                reason="Next ready stage selected by dependency order.",
                timeout_minutes=stage.timeout_minutes,
            )

        last_stage_id = plan.stages[-1].stage_id if plan.stages else "unknown_stage"
        return ExecutionDecision(
            run_id=run.run_id,
            stage_id=last_stage_id,
            decision_type=DecisionType.MARK_COMPLETED,
            reason="All planned stages completed.",
        )
