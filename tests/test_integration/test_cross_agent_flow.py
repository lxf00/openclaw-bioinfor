from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scripts.inbox_dispatch import dispatch_messages


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


def _message(target: str) -> str:
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


def test_inbox_dispatch_updates_target_context(tmp_path: Path) -> None:
    inbox = tmp_path / "shared_memory" / "inbox"
    agents = tmp_path / "agents"
    (inbox / "archive").mkdir(parents=True, exist_ok=True)
    (agents / "model_agent").mkdir(parents=True, exist_ok=True)

    ctx = agents / "model_agent" / "active_context.md"
    ctx.write_text(ACTIVE_CONTEXT_TEMPLATE, encoding="utf-8")

    msg = inbox / "2026-03-21T10-00-00_data_agent_to_model_agent.md"
    msg.write_text(_message("model_agent"), encoding="utf-8")

    report = dispatch_messages(inbox, agents, dry_run=False)
    assert report["processed"] == 1
    assert (inbox / "archive" / msg.name).exists()

    updated = ctx.read_text(encoding="utf-8")
    assert "## Incoming Messages" in updated
    assert "data_agent" in updated
