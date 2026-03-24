"""Execution plan builders for the harness."""

from __future__ import annotations

from bioopenclaw.harness.models import ExecutionPlan, StageSpec, TaskArchetype, TaskSpec


DEFAULT_STAGE_BLUEPRINT: list[tuple[str, str, str]] = [
    ("scouting", "Collect candidate models, methods, and references.", "scout_agent"),
    ("hypothesis_design", "Turn findings into a concrete research plan.", "research_agent"),
    ("data_preparation", "Acquire and prepare the required datasets.", "data_agent"),
    ("modeling_or_analysis", "Train, adapt, or analyze with selected models.", "model_agent"),
    ("result_synthesis", "Summarize conclusions, risks, and follow-ups.", "research_agent"),
]


class DefaultPlanner:
    """Build a task-aware stage plan using inferred research archetypes."""

    def build_plan(self, task_spec: TaskSpec) -> ExecutionPlan:
        archetype = infer_task_archetype(task_spec)
        stages = self._build_archetype_plan(task_spec, archetype)
        rationale = (
            f"Planned as '{archetype.value}' based on task title/goal, "
            "declared constraints, and structured inputs."
        )
        return ExecutionPlan(
            task_id=task_spec.task_id,
            stages=stages,
            archetype=archetype,
            rationale=rationale,
        )

    def _build_archetype_plan(self, task_spec: TaskSpec, archetype: TaskArchetype) -> list[StageSpec]:
        if archetype == TaskArchetype.LITERATURE_REVIEW:
            return self._literature_review_plan(task_spec)
        if archetype == TaskArchetype.DATA_PREPARATION:
            return self._data_preparation_plan(task_spec)
        if archetype == TaskArchetype.MODEL_TUNING:
            return self._model_tuning_plan(task_spec)
        if archetype == TaskArchetype.MONITORING:
            return self._monitoring_plan(task_spec)
        return self._full_pipeline_plan(task_spec)

    def _full_pipeline_plan(self, task_spec: TaskSpec) -> list[StageSpec]:
        stages: list[StageSpec] = []
        previous_stage_id: str | None = None

        keywords = _task_keywords(task_spec)
        base_model = _resolve_base_model(task_spec)
        for name, description, owner_agent in DEFAULT_STAGE_BLUEPRINT:
            tool_name = None
            tool_args: dict[str, object] = {}
            if name == "scouting":
                tool_name = "scan_arxiv_papers"
                tool_args = {"query": " ".join(keywords[:4]), "max_results": 10}
            elif name == "hypothesis_design":
                tool_name = "generate_hypothesis"
                tool_args = {
                    "background": task_spec.goal,
                    "observation": str(task_spec.inputs.get("observation", task_spec.goal)),
                }
            elif name == "data_preparation":
                tool_name = "search_datasets"
                tool_args = {
                    "keywords": keywords[:4] or ["single-cell"],
                    "organism": task_spec.constraints.get("organism", "Homo sapiens"),
                }
            elif name == "modeling_or_analysis":
                tool_name = "create_lora_config"
                tool_args = {"base_model": base_model}

            stage = StageSpec(
                name=name,
                description=description,
                owner_agent=owner_agent,
                depends_on=[previous_stage_id] if previous_stage_id else [],
                expected_outputs=[f"{name}_summary"],
                completion_checks=[f"{name}_summary_available"],
                tool_name=tool_name,
                tool_args=tool_args,
                metadata={"archetype": TaskArchetype.FULL_PIPELINE.value},
                retry_limit=task_spec.budget.max_retries_per_stage,
            )
            stages.append(stage)
            previous_stage_id = stage.stage_id
        return stages

    def _literature_review_plan(self, task_spec: TaskSpec) -> list[StageSpec]:
        review = StageSpec(
            name="literature_review",
            description="Retrieve the most relevant papers and summaries.",
            owner_agent="research_agent",
            expected_outputs=["literature_review_summary"],
            completion_checks=["literature_review_summary_available"],
            tool_name="search_pubmed",
            tool_args={"query": task_spec.goal, "max_results": 10},
            metadata={"archetype": TaskArchetype.LITERATURE_REVIEW.value},
            retry_limit=task_spec.budget.max_retries_per_stage,
        )
        hypothesis = StageSpec(
            name="hypothesis_design",
            description="Draft a scientific hypothesis from the reviewed literature.",
            owner_agent="research_agent",
            depends_on=[review.stage_id],
            expected_outputs=["hypothesis_design_summary"],
            completion_checks=["hypothesis_design_summary_available"],
            tool_name="generate_hypothesis",
            tool_args={
                "background": task_spec.goal,
                "observation": str(task_spec.inputs.get("observation", task_spec.goal)),
            },
            metadata={"archetype": TaskArchetype.LITERATURE_REVIEW.value},
            retry_limit=task_spec.budget.max_retries_per_stage,
        )
        return [review, hypothesis]

    def _data_preparation_plan(self, task_spec: TaskSpec) -> list[StageSpec]:
        dataset_query = StageSpec(
            name="dataset_discovery",
            description="Search candidate datasets that match the requested biology.",
            owner_agent="data_agent",
            expected_outputs=["dataset_discovery_summary"],
            completion_checks=["dataset_discovery_summary_available"],
            tool_name="search_datasets",
            tool_args={
                "keywords": _task_keywords(task_spec)[:4] or ["single-cell"],
                "organism": task_spec.constraints.get("organism", "Homo sapiens"),
            },
            metadata={"archetype": TaskArchetype.DATA_PREPARATION.value},
            retry_limit=task_spec.budget.max_retries_per_stage,
        )
        qc_stage = StageSpec(
            name="qc_design",
            description="Inspect and prepare the selected dataset for downstream analysis.",
            owner_agent="data_agent",
            depends_on=[dataset_query.stage_id],
            expected_outputs=["qc_design_summary"],
            completion_checks=["qc_design_summary_available"],
            tool_name="inspect_dataset",
            tool_args={"file_path": str(task_spec.inputs.get("file_path", "dataset.h5ad"))},
            metadata={"archetype": TaskArchetype.DATA_PREPARATION.value},
            retry_limit=task_spec.budget.max_retries_per_stage,
        )
        return [dataset_query, qc_stage]

    def _model_tuning_plan(self, task_spec: TaskSpec) -> list[StageSpec]:
        config_stage = StageSpec(
            name="lora_configuration",
            description="Generate an adapter training configuration for the chosen model.",
            owner_agent="model_agent",
            expected_outputs=["lora_configuration_summary"],
            completion_checks=["lora_configuration_summary_available"],
            tool_name="create_lora_config",
            tool_args={"base_model": _resolve_base_model(task_spec)},
            metadata={"archetype": TaskArchetype.MODEL_TUNING.value},
            retry_limit=task_spec.budget.max_retries_per_stage,
        )
        download_stage = StageSpec(
            name="model_download",
            description="Fetch the target model weights or repo snapshot.",
            owner_agent="model_agent",
            depends_on=[config_stage.stage_id],
            expected_outputs=["model_download_summary"],
            completion_checks=["model_download_summary_available"],
            tool_name="download_model",
            tool_args={"model_id": _resolve_base_model(task_spec)},
            metadata={"archetype": TaskArchetype.MODEL_TUNING.value},
            retry_limit=task_spec.budget.max_retries_per_stage,
        )
        return [config_stage, download_stage]

    def _monitoring_plan(self, task_spec: TaskSpec) -> list[StageSpec]:
        scout = StageSpec(
            name="registry_scan",
            description="Scan recent model and paper activity for candidate updates.",
            owner_agent="scout_agent",
            expected_outputs=["registry_scan_summary"],
            completion_checks=["registry_scan_summary_available"],
            tool_name="scan_huggingface_models",
            tool_args={"tags": _task_keywords(task_spec)[:3] or ["single-cell"], "limit": 10},
            metadata={"archetype": TaskArchetype.MONITORING.value},
            retry_limit=task_spec.budget.max_retries_per_stage,
        )
        arxiv = StageSpec(
            name="preprint_scan",
            description="Review recent arXiv activity relevant to the monitoring task.",
            owner_agent="scout_agent",
            depends_on=[scout.stage_id],
            expected_outputs=["preprint_scan_summary"],
            completion_checks=["preprint_scan_summary_available"],
            tool_name="scan_arxiv_papers",
            tool_args={"query": " ".join(_task_keywords(task_spec)[:4]), "max_results": 10},
            metadata={"archetype": TaskArchetype.MONITORING.value},
            retry_limit=task_spec.budget.max_retries_per_stage,
        )
        return [scout, arxiv]


def infer_task_archetype(task_spec: TaskSpec) -> TaskArchetype:
    """Infer the most likely harness workflow archetype for the task."""
    if task_spec.task_type is not None:
        return task_spec.task_type

    explicit = task_spec.constraints.get("task_type") or task_spec.inputs.get("task_type")
    if explicit:
        try:
            return TaskArchetype(str(explicit))
        except ValueError:
            pass

    text = " ".join([
        task_spec.title,
        task_spec.goal,
        " ".join(_task_keywords(task_spec)),
    ]).lower()

    if any(word in text for word in ["lora", "qlora", "fine-tune", "finetune", "training", "checkpoint"]):
        return TaskArchetype.MODEL_TUNING
    if any(word in text for word in ["literature", "pubmed", "paper", "hypothesis", "statistical"]):
        return TaskArchetype.LITERATURE_REVIEW
    if any(word in text for word in ["qc", "dataset", "geo", "tcga", "cellxgene", "h5ad", "normalize"]):
        return TaskArchetype.DATA_PREPARATION
    if any(word in text for word in ["monitor", "registry", "huggingface", "arxiv", "benchmark", "scan"]):
        return TaskArchetype.MONITORING
    return TaskArchetype.FULL_PIPELINE


def _task_keywords(task_spec: TaskSpec) -> list[str]:
    raw_keywords = task_spec.constraints.get("keywords") or task_spec.inputs.get("keywords")
    if isinstance(raw_keywords, list):
        return [str(keyword) for keyword in raw_keywords]

    text = " ".join(filter(None, [task_spec.title, task_spec.goal]))
    tokens = [
        token.strip(" ,.;:()[]{}").lower()
        for token in text.split()
    ]
    keywords: list[str] = []
    for token in tokens:
        if len(token) < 4:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords[:8]


def _resolve_base_model(task_spec: TaskSpec) -> str:
    for source in (task_spec.inputs, task_spec.constraints):
        for key in ("base_model", "model_id", "model_name"):
            value = source.get(key)
            if value:
                return str(value)
    return "scGPT"
