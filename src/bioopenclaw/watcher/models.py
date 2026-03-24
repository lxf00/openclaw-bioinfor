"""Watcher data models — detection results, steering messages, correction records."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    REPEATED_TOOL_CALL = "repeated_tool_call"
    MAX_ROUNDS_EXCEEDED = "max_rounds_exceeded"
    OUTPUT_STAGNATION = "output_stagnation"
    BLOCKED_STALE = "blocked_stale"
    MEMORY_QUALITY = "memory_quality"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DetectionResult(BaseModel):
    """Result of a Watcher detection check."""

    level: int = Field(..., ge=1, le=3, description="Detection level (1=hard rule, 2=soft rule, 3=preventive)")
    trigger_type: TriggerType
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    target_agent: str = ""


class SteeringMessage(BaseModel):
    """A corrective message to be injected into an agent's workflow."""

    target_agent: str
    message: str
    priority: Priority = Priority.MEDIUM
    created_at: datetime = Field(default_factory=datetime.now)
    trigger: DetectionResult
    delivered: bool = False


class CorrectionRecord(BaseModel):
    """A record of a correction action taken by the Watcher."""

    timestamp: datetime = Field(default_factory=datetime.now)
    target_agent: str
    trigger_type: TriggerType
    trigger_details: str
    action: str
    effect: str = "待验证"
    domain_tags: list[str] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM
