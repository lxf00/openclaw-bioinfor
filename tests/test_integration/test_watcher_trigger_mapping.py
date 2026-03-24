from __future__ import annotations

from bioopenclaw.watcher.models import TriggerType
from bioopenclaw.watcher.server import _normalize_trigger_type


def test_watcher_trigger_type_alias_mapping() -> None:
    assert _normalize_trigger_type("loop_detection") == TriggerType.REPEATED_TOOL_CALL
    assert _normalize_trigger_type("stagnation") == TriggerType.OUTPUT_STAGNATION
    assert _normalize_trigger_type("memory_quality") == TriggerType.MEMORY_QUALITY


def test_watcher_trigger_type_canonical_mapping() -> None:
    assert _normalize_trigger_type("repeated_tool_call") == TriggerType.REPEATED_TOOL_CALL
    assert _normalize_trigger_type("max_rounds_exceeded") == TriggerType.MAX_ROUNDS_EXCEEDED
    assert _normalize_trigger_type("output_stagnation") == TriggerType.OUTPUT_STAGNATION
    assert _normalize_trigger_type("blocked_stale") == TriggerType.BLOCKED_STALE


def test_watcher_trigger_type_default_fallback() -> None:
    assert _normalize_trigger_type("unknown_trigger") == TriggerType.REPEATED_TOOL_CALL
