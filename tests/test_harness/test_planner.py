from __future__ import annotations

from bioopenclaw.harness.models import TaskArchetype, TaskSpec
from bioopenclaw.harness.planner import DefaultPlanner, infer_task_archetype
from bioopenclaw.harness.scheduler import DefaultScheduler


def test_infer_task_archetype_for_data_preparation() -> None:
    spec = TaskSpec(
        title="QC a GEO single-cell dataset",
        goal="Search datasets and prepare a GEO h5ad file for QC and normalization.",
        success_criteria=["dataset prepared"],
    )

    assert infer_task_archetype(spec) == TaskArchetype.DATA_PREPARATION


def test_dynamic_planner_builds_model_tuning_plan_with_tools() -> None:
    planner = DefaultPlanner()
    spec = TaskSpec(
        title="LoRA fine-tune scGPT",
        goal="Prepare a LoRA training workflow for scGPT.",
        success_criteria=["config ready"],
        inputs={"base_model": "scGPT"},
    )

    plan = planner.build_plan(spec)

    assert plan.archetype == TaskArchetype.MODEL_TUNING
    assert [stage.owner_agent for stage in plan.stages] == ["model_agent", "model_agent"]
    assert plan.stages[0].tool_name == "create_lora_config"
    assert plan.stages[0].tool_args["base_model"] == "scGPT"
    assert plan.stages[1].tool_name == "download_model"


def test_scheduler_propagates_stage_tool_selection() -> None:
    planner = DefaultPlanner()
    scheduler = DefaultScheduler()
    spec = TaskSpec(
        title="Review literature and generate a hypothesis",
        goal="Run a literature review on T cell exhaustion and draft a hypothesis.",
        success_criteria=["hypothesis drafted"],
    )
    plan = planner.build_plan(spec)
    run = __import__("bioopenclaw.harness.models", fromlist=["TaskRun"]).TaskRun(
        task_id=spec.task_id,
        plan_id=plan.plan_id,
    )
    state = __import__("bioopenclaw.harness.models", fromlist=["TaskState"]).TaskState(run_id=run.run_id)

    decision = scheduler.decide(run, state, plan)

    assert plan.archetype == TaskArchetype.LITERATURE_REVIEW
    assert decision.required_inputs["tool_name"] == "search_pubmed"
    assert "tool_args" in decision.required_inputs
    assert decision.target_agent == "research_agent"
