"""Watcher three-layer detection engine.

Layer 1 (hard rules): Repeated tool calls, max rounds exceeded.
Layer 2 (soft rules): Output stagnation via text similarity.
Layer 3 (preventive): Reserved for memory quality checks.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from difflib import SequenceMatcher
from typing import Any

from bioopenclaw.watcher.config import WatcherConfig, get_config
from bioopenclaw.watcher.models import DetectionResult, TriggerType

logger = logging.getLogger(__name__)


class WatcherDetector:
    """Three-layer detection engine for monitoring agent behavior."""

    def __init__(self, config: WatcherConfig | None = None) -> None:
        self.config = config or get_config()
        self.tool_call_history: list[dict[str, Any]] = []
        self.tool_hash_history: list[str] = []
        self.output_history: list[str] = []
        self.total_tool_calls: int = 0

    def record_tool_call(
        self,
        tool_name: str,
        params: dict[str, Any],
        agent_name: str = "",
    ) -> DetectionResult | None:
        """Record a tool call and check for Level 1 anomalies.

        Returns a DetectionResult if an anomaly is detected, otherwise None.
        """
        self.total_tool_calls += 1

        call_record = {"tool_name": tool_name, "params": params, "agent": agent_name}
        self.tool_call_history.append(call_record)

        call_hash = self._hash_call(tool_name, params)
        self.tool_hash_history.append(call_hash)

        if self.total_tool_calls > self.config.max_tool_rounds:
            return DetectionResult(
                level=1,
                trigger_type=TriggerType.MAX_ROUNDS_EXCEEDED,
                message=(
                    f"Agent {agent_name or 'unknown'} has exceeded the maximum "
                    f"tool call limit ({self.config.max_tool_rounds}). "
                    f"Total calls: {self.total_tool_calls}."
                ),
                details={
                    "total_calls": self.total_tool_calls,
                    "max_rounds": self.config.max_tool_rounds,
                    "last_tool": tool_name,
                },
                target_agent=agent_name,
            )

        window = self.tool_hash_history[-self.config.hash_window:]
        counts = Counter(window)
        for h, count in counts.items():
            if count >= self.config.repeat_threshold and h == call_hash:
                repeated_call = self.tool_call_history[-1]
                return DetectionResult(
                    level=1,
                    trigger_type=TriggerType.REPEATED_TOOL_CALL,
                    message=(
                        f"Agent {agent_name or 'unknown'} has called "
                        f"'{tool_name}' with identical parameters "
                        f"{count} times in the last {len(window)} calls."
                    ),
                    details={
                        "tool_name": tool_name,
                        "repeat_count": count,
                        "window_size": len(window),
                        "params_snapshot": {
                            k: str(v)[:100] for k, v in params.items()
                        },
                    },
                    target_agent=agent_name,
                )

        return None

    def record_output(
        self,
        output: str,
        agent_name: str = "",
    ) -> DetectionResult | None:
        """Record an agent output and check for Level 2 stagnation.

        Returns a DetectionResult if stagnation is detected, otherwise None.
        """
        self.output_history.append(output)

        if len(self.output_history) < self.config.stall_window:
            return None

        recent = self.output_history[-self.config.stall_window:]
        similarities: list[float] = []
        for i in range(len(recent)):
            for j in range(i + 1, len(recent)):
                sim = SequenceMatcher(None, recent[i], recent[j]).ratio()
                similarities.append(sim)

        if not similarities:
            return None

        avg_similarity = sum(similarities) / len(similarities)

        if avg_similarity > self.config.similarity_threshold:
            return DetectionResult(
                level=2,
                trigger_type=TriggerType.OUTPUT_STAGNATION,
                message=(
                    f"Agent {agent_name or 'unknown'} appears stalled: "
                    f"average output similarity over the last "
                    f"{self.config.stall_window} rounds is "
                    f"{avg_similarity:.3f} (threshold: {self.config.similarity_threshold})."
                ),
                details={
                    "avg_similarity": round(avg_similarity, 4),
                    "threshold": self.config.similarity_threshold,
                    "window_size": self.config.stall_window,
                    "sample_length": len(recent[-1]),
                },
                target_agent=agent_name,
            )

        return None

    def reset(self) -> None:
        """Clear all history. Call when a new task begins."""
        self.tool_call_history.clear()
        self.tool_hash_history.clear()
        self.output_history.clear()
        self.total_tool_calls = 0
        logger.info("Watcher detector state reset")

    @staticmethod
    def _hash_call(tool_name: str, params: dict[str, Any]) -> str:
        """Create a deterministic hash of a tool call for dedup detection."""
        canonical = json.dumps(
            {"tool": tool_name, "params": params},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
