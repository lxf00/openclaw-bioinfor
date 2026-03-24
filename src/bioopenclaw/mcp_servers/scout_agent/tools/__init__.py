"""Scout Agent MCP tools."""

from bioopenclaw.mcp_servers.scout_agent.tools.hf_monitor import scan_huggingface_models
from bioopenclaw.mcp_servers.scout_agent.tools.arxiv_monitor import scan_arxiv_papers
from bioopenclaw.mcp_servers.scout_agent.tools.registry_writer import register_model

__all__ = [
    "scan_huggingface_models",
    "scan_arxiv_papers",
    "register_model",
]
