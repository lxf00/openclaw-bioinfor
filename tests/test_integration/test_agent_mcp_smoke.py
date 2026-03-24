from __future__ import annotations

import importlib
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


SERVERS = {
    "data-agent": "bioopenclaw.mcp_servers.data_agent.server",
    "scout-agent": "bioopenclaw.mcp_servers.scout_agent.server",
    "model-agent": "bioopenclaw.mcp_servers.model_agent.server",
    "research-agent": "bioopenclaw.mcp_servers.research_agent.server",
    "watcher": "bioopenclaw.watcher.server",
}


def test_all_servers_register_tools_and_handlers() -> None:
    for name, module_path in SERVERS.items():
        module = importlib.import_module(module_path)
        tools = getattr(module, "TOOLS")
        handlers = getattr(module, "TOOL_HANDLERS")

        assert tools, f"{name} should register at least one tool"
        tool_names = [t.name for t in tools]

        for tool_name in tool_names:
            assert tool_name in handlers, f"{name} missing handler for tool {tool_name}"

        for handler_name in handlers.keys():
            assert handler_name in tool_names, (
                f"{name} has handler '{handler_name}' not present in TOOLS"
            )
