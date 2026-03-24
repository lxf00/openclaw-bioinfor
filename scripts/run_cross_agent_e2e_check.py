#!/usr/bin/env python3
"""Cross-agent E2E check for inbox dispatch + watcher logging.

This check uses temporary files and does not require external services.

Usage:
    python scripts/run_cross_agent_e2e_check.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.inbox_dispatch import dispatch_messages
from bioopenclaw.watcher.models import CorrectionRecord, Priority, TriggerType
from bioopenclaw.watcher.steering import SteeringQueue


ACTIVE_CONTEXT_TEMPLATE = """---
last_session: 2026-03-21T00:00:00
---

## Current Focus
（暂无）

## Blocked
（暂无）

## Next Steps
（暂无）

## Recent Decisions
（暂无）
"""


def _make_message(target: str) -> str:
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    return f"""---
from: data_agent
to: {target}
priority: medium
created: {now}
type: handoff
---

# Handoff

Data processing completed. Please continue.
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        inbox = root / "shared_memory" / "inbox"
        agents = root / "agents"
        watcher_log_dir = agents / "watcher" / "corrections_log"

        (inbox / "archive").mkdir(parents=True, exist_ok=True)
        (agents / "model_agent").mkdir(parents=True, exist_ok=True)
        watcher_log_dir.mkdir(parents=True, exist_ok=True)

        active_context_path = agents / "model_agent" / "active_context.md"
        active_context_path.write_text(ACTIVE_CONTEXT_TEMPLATE, encoding="utf-8")

        msg_path = inbox / "2026-03-21T10-00-00_data_agent_to_model_agent.md"
        msg_path.write_text(_make_message("model_agent"), encoding="utf-8")

        report = dispatch_messages(inbox, agents, dry_run=False)
        assert report["processed"] == 1, f"Expected 1 processed message, got {report}"
        assert (inbox / "archive" / msg_path.name).exists(), "Message should be archived"

        updated_context = active_context_path.read_text(encoding="utf-8")
        assert "Incoming Messages" in updated_context, "Incoming message section should be added"

        queue = SteeringQueue()
        # Route watcher writes into temp inbox via direct method call.
        # (write_inbox_message uses global config; here we validate correction logging only.)
        record = CorrectionRecord(
            target_agent="model_agent",
            trigger_type=TriggerType.REPEATED_TOOL_CALL,
            trigger_details="Repeated identical tool call 3 times",
            action="Injected steering message",
            effect="待验证",
            domain_tags=["loop", "routing"],
            priority=Priority.MEDIUM,
        )
        # monkey patch via attribute assignment for temp validation path
        from bioopenclaw.watcher import steering as steering_module

        original_get_config = steering_module.get_config

        class _Cfg:
            corrections_log_dir = str(watcher_log_dir)
            inbox_dir = str(inbox)

        steering_module.get_config = lambda: _Cfg()  # type: ignore[assignment]
        try:
            log_path = queue.log_correction(record)
        finally:
            steering_module.get_config = original_get_config  # type: ignore[assignment]

        assert log_path.exists(), "Watcher correction log should be created"
        assert "repeated_tool_call" in log_path.read_text(encoding="utf-8")

    print("E2E CHECK: PASSED")


if __name__ == "__main__":
    main()
