#!/usr/bin/env python3
"""Cross-agent MCP smoke test script.

Verifies that each agent server module imports correctly and registers
tools with matching handlers.

Usage:
    python scripts/run_agent_smoke_tests.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


SERVERS = {
    "data-agent": "bioopenclaw.mcp_servers.data_agent.server",
    "scout-agent": "bioopenclaw.mcp_servers.scout_agent.server",
    "model-agent": "bioopenclaw.mcp_servers.model_agent.server",
    "research-agent": "bioopenclaw.mcp_servers.research_agent.server",
    "watcher": "bioopenclaw.watcher.server",
}


def verify_server(name: str, module_path: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        module = importlib.import_module(module_path)
    except Exception as exc:
        return False, [f"{name}: import failed: {exc}"]

    tools = getattr(module, "TOOLS", None)
    handlers = getattr(module, "TOOL_HANDLERS", None)
    if tools is None or handlers is None:
        errors.append(f"{name}: missing TOOLS or TOOL_HANDLERS")
        return False, errors

    tool_names = [t.name for t in tools]
    if not tool_names:
        errors.append(f"{name}: no registered tools")
        return False, errors

    for tool_name in tool_names:
        if tool_name not in handlers:
            errors.append(f"{name}: tool '{tool_name}' has no handler")

    extra_handlers = [k for k in handlers.keys() if k not in tool_names]
    if extra_handlers:
        errors.append(f"{name}: extra handlers not in TOOLS: {extra_handlers}")

    return len(errors) == 0, errors


def main() -> None:
    print("=" * 68)
    print("BioOpenClaw — Cross-Agent MCP Smoke Tests")
    print("=" * 68)
    all_errors: list[str] = []

    for name, module_path in SERVERS.items():
        print(f"\n[{name}] {module_path}")
        ok, errors = verify_server(name, module_path)
        if ok:
            module = importlib.import_module(module_path)
            tool_names = [t.name for t in getattr(module, "TOOLS")]
            print(f"  OK  tools: {', '.join(tool_names)}")
        else:
            print("  FAIL")
            for err in errors:
                print(f"    - {err}")
            all_errors.extend(errors)

    print("\n" + "=" * 68)
    if all_errors:
        print(f"RESULT: FAILED ({len(all_errors)} issue(s))")
        sys.exit(1)
    print("RESULT: PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
