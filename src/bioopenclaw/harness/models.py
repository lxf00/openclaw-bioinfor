"""Core data models for the BioOpenClaw harness control plane."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    """Create a readable unique identifier for harness records."""
    return f"{prefix}_{uuid4().hex[:12]}"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskArchetype(str, Enum):
    FULL_PIPELINE = "full_pipeline"
    LITERATURE_REVIEW = "literature_review"
    DATA_PREPARATION = "data_preparation"
    MODEL_TUNING = "model_tuning"
    MONITORING = "monitoring"


class StageStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DecisionType(str, Enum):
    INVOKE_AGENT = "invoke_agent"
    RETRY_STAGE = "retry_stage"
    ROLLBACK_STAGE = "rollback_stage"
    WAIT_FOR_INPUT = "wait_for_input"
    TERMINATE_RUN = "terminate_run"
    MARK_COMPLETED = "mark_completed"


class StepStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class AgentResultStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"


class ToolCallStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    SCHEMA_ERROR = "schema_error"
    TRANSPORT_ERROR = "transport_error"


class ArtifactKind(str, Enum):
    DATASET = "dataset"
    MODEL = "model"
    REPORT = "report"
    LITERATURE_NOTE = "literature_note"
    HYPOTHESIS = "hypothesis"
    RESULT_TABLE = "result_table"
    LOG = "log"
    OTHER = "other"


class HandoffStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class MemoryScope(str, Enum):
    TASK = "task"
    AGENT = "agent"
    SHARED = "shared"
    WATCHER = "watcher"


class TriggerSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TriggerType(str, Enum):
    REPEATED_TOOL_CALL = "repeated_tool_call"
    NO_PROGRESS = "no_progress"
    HANDOFF_BOUNCE = "handoff_bounce"
    SCHEMA_MISMATCH = "schema_mismatch"
    EXCESSIVE_RETRY = "excessive_retry"
    MISSING_ARTIFACT = "missing_artifact"
    CONFLICTING_RESULTS = "conflicting_results"


class CorrectionAction(str, Enum):
    RETRY = "retry"
    REROUTE = "reroute"
    ROLLBACK = "rollback"
    NARROW_SCOPE = "narrow_scope"
    REQUEST_VALIDATION = "request_validation"
    FREEZE_TASK = "freeze_task"
    TERMINATE = "terminate"


class BudgetSpec(BaseModel):
    max_steps: int | None = None
    max_tool_calls: int | None = None
    max_runtime_minutes: int | None = None
    max_retries_per_stage: int = 2
    max_total_failures: int = 5


class TaskSpec(BaseModel):
    task_id: str = Field(default_factory=lambda: new_id("task"))
    title: str
    goal: str
    success_criteria: list[str]
    task_type: TaskArchetype | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
    requested_by: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StageSpec(BaseModel):
    stage_id: str = Field(default_factory=lambda: new_id("stage"))
    name: str
    description: str
    owner_agent: str
    depends_on: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    completion_checks: list[str] = Field(default_factory=list)
    tool_name: str | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    retry_limit: int = 2
    timeout_minutes: int | None = None


class ExecutionPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: new_id("plan"))
    task_id: str
    stages: list[StageSpec]
    archetype: TaskArchetype = TaskArchetype.FULL_PIPELINE
    version: int = 1
    rationale: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TaskRun(BaseModel):
    run_id: str = Field(default_factory=lambda: new_id("run"))
    task_id: str
    plan_id: str
    status: RunStatus = RunStatus.CREATED
    current_stage_id: str | None = None
    current_agent: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class TaskState(BaseModel):
    run_id: str
    completed_stages: list[str] = Field(default_factory=list)
    active_stages: list[str] = Field(default_factory=list)
    blocked_stages: list[str] = Field(default_factory=list)
    failed_stages: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    open_handoffs: list[str] = Field(default_factory=list)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    tool_call_counts: dict[str, int] = Field(default_factory=dict)
    failure_count: int = 0
    loop_score: float = 0.0
    last_progress_at: datetime | None = None


class ExecutionDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: new_id("decision"))
    run_id: str
    stage_id: str
    decision_type: DecisionType
    target_agent: str | None = None
    intent: str = ""
    required_inputs: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    timeout_minutes: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ArtifactRef(BaseModel):
    artifact_id: str = Field(default_factory=lambda: new_id("artifact"))
    run_id: str
    kind: ArtifactKind
    name: str
    uri: str
    producer_agent: str
    stage_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Handoff(BaseModel):
    handoff_id: str = Field(default_factory=lambda: new_id("handoff"))
    run_id: str
    from_agent: str
    to_agent: str
    stage_id: str
    intent: str
    required_outputs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    note: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    status: HandoffStatus = HandoffStatus.OPEN
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MemoryRecord(BaseModel):
    memory_id: str = Field(default_factory=lambda: new_id("memory"))
    run_id: str
    scope: MemoryScope
    owner: str
    title: str
    content_ref: str
    tags: list[str] = Field(default_factory=list)
    source_step_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ToolCallRecord(BaseModel):
    tool_call_id: str = Field(default_factory=lambda: new_id("tool"))
    run_id: str
    stage_id: str
    agent: str
    server_name: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: ToolCallStatus
    response_summary: str = ""
    error_type: str | None = None
    latency_ms: int | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class AgentInvocation(BaseModel):
    invocation_id: str = Field(default_factory=lambda: new_id("invoke"))
    run_id: str
    stage_id: str
    target_agent: str
    objective: str
    context_refs: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    required_outputs: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    invocation_id: str
    status: AgentResultStatus
    summary: str
    outputs: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    proposed_handoffs: list[Handoff] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    memories: list[MemoryRecord] = Field(default_factory=list)
    confidence: float | None = None


class StepRecord(BaseModel):
    step_id: str = Field(default_factory=lambda: new_id("step"))
    run_id: str
    stage_id: str
    agent: str
    decision_id: str
    status: StepStatus
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    summary: str = ""
    produced_artifacts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    invocation_id: str | None = None


class WatcherTrigger(BaseModel):
    trigger_id: str = Field(default_factory=lambda: new_id("trigger"))
    run_id: str
    stage_id: str | None = None
    trigger_type: TriggerType
    severity: TriggerSeverity
    evidence_refs: list[str] = Field(default_factory=list)
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CorrectionProposal(BaseModel):
    proposal_id: str = Field(default_factory=lambda: new_id("proposal"))
    run_id: str
    trigger_id: str
    action: CorrectionAction
    target_stage_id: str | None = None
    target_agent: str | None = None
    reason: str = ""
    confidence: float | None = None


class WatcherEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("event"))
    run_id: str
    trigger_id: str
    proposal_id: str | None = None
    applied_action: str
    outcome: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FinalReport(BaseModel):
    run_id: str
    task_id: str
    status: RunStatus
    executive_summary: str
    key_findings: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    unresolved_risks: list[str] = Field(default_factory=list)
    watcher_summary: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class TaskSnapshot(BaseModel):
    run: TaskRun
    state: TaskState
    recent_steps: list[StepRecord] = Field(default_factory=list)
    open_handoffs: list[Handoff] = Field(default_factory=list)
    recent_triggers: list[WatcherTrigger] = Field(default_factory=list)


class GovernanceOutcome(BaseModel):
    health: str = "healthy"
    triggers: list[WatcherTrigger] = Field(default_factory=list)
    proposals: list[CorrectionProposal] = Field(default_factory=list)


class TickResult(BaseModel):
    run: TaskRun
    state: TaskState
    decision: ExecutionDecision
    step: StepRecord | None = None
    governance: GovernanceOutcome = Field(default_factory=GovernanceOutcome)
