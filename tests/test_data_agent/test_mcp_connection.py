"""Tests for MCP server registration and tool dispatch."""

from __future__ import annotations

import pytest


class TestMCPServerRegistration:
    def test_all_tools_registered(self) -> None:
        from bioopenclaw.mcp_servers.data_agent.server import TOOLS, TOOL_HANDLERS

        tool_names = {t.name for t in TOOLS}
        handler_names = set(TOOL_HANDLERS.keys())

        assert tool_names == handler_names, (
            f"Mismatch between TOOLS and TOOL_HANDLERS: "
            f"tools_only={tool_names - handler_names}, "
            f"handlers_only={handler_names - tool_names}"
        )

    def test_expected_tool_count(self) -> None:
        from bioopenclaw.mcp_servers.data_agent.server import TOOLS

        assert len(TOOLS) >= 17, f"Expected >= 17 tools, got {len(TOOLS)}"

    def test_all_tools_have_schemas(self) -> None:
        from bioopenclaw.mcp_servers.data_agent.server import TOOLS

        for tool in TOOLS:
            assert tool.inputSchema is not None, f"Tool '{tool.name}' missing inputSchema"
            assert tool.inputSchema.get("type") == "object", (
                f"Tool '{tool.name}' schema must be type=object"
            )

    def test_all_handlers_are_callable(self) -> None:
        from bioopenclaw.mcp_servers.data_agent.server import TOOL_HANDLERS

        for name, handler in TOOL_HANDLERS.items():
            assert callable(handler), f"Handler for '{name}' is not callable"

    def test_tool_names_match(self) -> None:
        from bioopenclaw.mcp_servers.data_agent.server import TOOLS

        expected = {
            "run_scanpy_qc",
            "download_geo_data",
            "inspect_dataset",
            "normalize_data",
            "convert_data_format",
            "search_datasets",
            "download_tcga_data",
            "query_cellxgene",
            "run_batch_correction",
            "generate_qc_report",
            "run_pipeline",
            "query_uniprot",
            "query_pdb",
            "process_multiome",
            "create_snapshot",
            "list_versions",
            "restore_version",
        }

        registered = {t.name for t in TOOLS}
        missing = expected - registered
        assert not missing, f"Missing tools: {missing}"
