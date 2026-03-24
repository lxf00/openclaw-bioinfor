"""Steering queue — manages corrective messages and logs corrections."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from bioopenclaw.watcher.config import get_config
from bioopenclaw.watcher.models import (
    CorrectionRecord,
    DetectionResult,
    Priority,
    SteeringMessage,
)

logger = logging.getLogger(__name__)


class SteeringQueue:
    """Queue for corrective (steering) messages directed at agents."""

    def __init__(self) -> None:
        self.queue: list[SteeringMessage] = []

    def inject(
        self,
        target_agent: str,
        message: str,
        priority: Priority | str = Priority.MEDIUM,
        trigger: DetectionResult | None = None,
    ) -> SteeringMessage:
        """Add a steering message to the queue."""
        if isinstance(priority, str):
            priority = Priority(priority)

        if trigger is None:
            from bioopenclaw.watcher.models import TriggerType
            trigger = DetectionResult(
                level=1,
                trigger_type=TriggerType.REPEATED_TOOL_CALL,
                message="Manual injection",
                target_agent=target_agent,
            )

        msg = SteeringMessage(
            target_agent=target_agent,
            message=message,
            priority=priority,
            trigger=trigger,
        )
        self.queue.append(msg)
        logger.info(
            "Steering message injected for %s (priority=%s)",
            target_agent, priority.value,
        )
        return msg

    def pop(self, target_agent: str) -> SteeringMessage | None:
        """Retrieve and remove the next steering message for *target_agent*.

        Messages are returned in priority order (high > medium > low),
        then by creation time (oldest first).
        """
        priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}

        candidates = [
            (i, m) for i, m in enumerate(self.queue)
            if m.target_agent == target_agent and not m.delivered
        ]

        if not candidates:
            return None

        candidates.sort(key=lambda x: (
            priority_order.get(x[1].priority, 99),
            x[1].created_at,
        ))

        idx, msg = candidates[0]
        msg.delivered = True
        self.queue.pop(idx)
        return msg

    def peek(self, target_agent: str) -> list[SteeringMessage]:
        """Preview pending messages for *target_agent* without removing them."""
        return [
            m for m in self.queue
            if m.target_agent == target_agent and not m.delivered
        ]

    def log_correction(self, record: CorrectionRecord) -> Path:
        """Write a correction record to ``agents/watcher/corrections_log/``.

        Returns the path to the log file.
        """
        cfg = get_config()
        log_dir = Path(cfg.corrections_log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        today = record.timestamp.strftime("%Y-%m-%d")
        log_file = log_dir / f"{today}.md"

        time_str = record.timestamp.strftime("%H:%M")
        tags_str = ", ".join(record.domain_tags) if record.domain_tags else "general"

        entry = (
            f"\n## {time_str} — {record.target_agent} {record.trigger_type.value}\n"
            f"\n"
            f"- **触发条件**: {record.trigger_details}\n"
            f"- **纠偏措施**: {record.action}\n"
            f"- **效果**: {record.effect}\n"
            f"- **领域标签**: {tags_str}\n"
            f"- **优先级**: {record.priority.value}\n"
        )

        if log_file.exists():
            content = log_file.read_text(encoding="utf-8")
            content += entry
        else:
            header = (
                f"# Watcher Corrections Log — {today}\n"
                f"\n"
                f"> 自动生成，记录所有纠偏操作。\n"
            )
            content = header + entry

        log_file.write_text(content, encoding="utf-8")
        logger.info("Correction logged to %s", log_file)
        return log_file

    def write_inbox_message(
        self,
        target_agent: str,
        message: str,
        priority: Priority | str = Priority.MEDIUM,
        trigger_type: str = "loop_detection",
    ) -> Path:
        """Write a steering message to ``shared_memory/inbox/`` as a Markdown file."""
        if isinstance(priority, str):
            priority = Priority(priority)

        cfg = get_config()
        inbox_dir = Path(cfg.inbox_dir)
        inbox_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        filename = f"{now.strftime('%Y-%m-%dT%H-%M-%S')}_watcher_to_{target_agent}.md"
        filepath = inbox_dir / filename

        content = (
            f"---\n"
            f"from: watcher\n"
            f"to: {target_agent}\n"
            f"priority: {priority.value}\n"
            f"created: {now.isoformat()}\n"
            f"type: steering\n"
            f"trigger: {trigger_type}\n"
            f"---\n"
            f"\n"
            f"# Watcher Steering Message\n"
            f"\n"
            f"{message}\n"
        )

        filepath.write_text(content, encoding="utf-8")
        logger.info("Inbox message written: %s", filepath)
        return filepath
