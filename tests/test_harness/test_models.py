from __future__ import annotations

from bioopenclaw.harness.models import BudgetSpec, StageSpec, TaskPriority, TaskSpec


def test_task_spec_defaults_and_stage_retry_limit() -> None:
    spec = TaskSpec(
        title="End-to-end single-cell workflow",
        goal="Run a complete multi-agent analysis workflow.",
        success_criteria=["final report written"],
        priority=TaskPriority.HIGH,
        budget=BudgetSpec(max_retries_per_stage=4),
    )
    stage = StageSpec(
        name="data_preparation",
        description="Prepare datasets.",
        owner_agent="data_agent",
        retry_limit=spec.budget.max_retries_per_stage,
    )

    assert spec.task_id.startswith("task_")
    assert stage.stage_id.startswith("stage_")
    assert stage.retry_limit == 4
