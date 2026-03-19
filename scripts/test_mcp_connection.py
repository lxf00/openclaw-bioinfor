#!/usr/bin/env python3
"""MCP connection verification script.

Validates that the Data Agent MCP Server starts correctly and all tools
are registered and callable.

Usage::

    python scripts/test_mcp_connection.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def verify_tools() -> bool:
    """Verify that all expected tools are importable and have correct signatures."""
    print("=" * 60)
    print("BioOpenClaw Data Agent — MCP Connection Verification")
    print("=" * 60)

    errors: list[str] = []

    # 1. Check imports
    print("\n[1/4] Checking imports...")
    try:
        from bioopenclaw.mcp_servers.data_agent.config import get_config
        print("  OK  config")
    except ImportError as e:
        errors.append(f"config: {e}")
        print(f"  FAIL config: {e}")

    expected_tools = [
        ("scanpy_qc", "run_scanpy_qc"),
        ("geo_download", "download_geo_data"),
        ("data_inspector", "inspect_dataset"),
        ("normalize", "normalize_data"),
        ("format_converter", "convert_data_format"),
        ("dataset_search", "search_datasets"),
        ("tcga_download", "download_tcga_data"),
        ("cellxgene_query", "query_cellxgene"),
        ("batch_correction", "run_batch_correction"),
        ("qc_report", "generate_qc_report"),
        ("pipeline", "run_pipeline"),
        ("uniprot_query", "query_uniprot"),
        ("pdb_query", "query_pdb"),
        ("multiome_process", "process_multiome"),
        ("version_manager", "create_snapshot"),
        ("version_manager", "list_versions"),
        ("version_manager", "restore_version"),
    ]

    for module, func in expected_tools:
        try:
            mod = __import__(
                f"bioopenclaw.mcp_servers.data_agent.tools.{module}",
                fromlist=[func],
            )
            fn = getattr(mod, func)
            assert callable(fn), f"{func} is not callable"
            print(f"  OK  {func}")
        except Exception as e:
            errors.append(f"{func}: {e}")
            print(f"  FAIL {func}: {e}")

    # 2. Check config
    print("\n[2/4] Checking configuration...")
    try:
        cfg = get_config()
        print(f"  Server name: {cfg.server_name}")
        print(f"  Port: {cfg.port}")
        print(f"  Data dir: {cfg.data_dir}")
        print(f"  Entrez email: {'SET' if cfg.entrez_email else 'NOT SET (required for GEO/PubMed)'}")
        print(f"  NCBI API key: {'SET' if cfg.ncbi_api_key else 'NOT SET (optional, improves rate limit)'}")
    except Exception as e:
        errors.append(f"config load: {e}")
        print(f"  FAIL: {e}")

    # 3. Check dependencies
    print("\n[3/4] Checking dependencies...")
    deps = {
        "mcp": "MCP SDK",
        "scanpy": "Scanpy",
        "anndata": "AnnData",
        "GEOparse": "GEOparse",
        "Bio": "BioPython",
        "requests": "Requests",
        "pydantic": "Pydantic",
        "pydantic_settings": "Pydantic Settings",
    }
    optional_deps = {
        "harmonypy": "Harmonypy (batch correction)",
        "scrublet": "Scrublet (doublet detection)",
        "scvi": "scvi-tools (deep batch correction)",
        "cellxgene_census": "CellxGene Census",
    }

    for module, name in deps.items():
        try:
            __import__(module)
            print(f"  OK  {name}")
        except ImportError:
            errors.append(f"Missing required dependency: {name}")
            print(f"  FAIL {name} — REQUIRED")

    for module, name in optional_deps.items():
        try:
            __import__(module)
            print(f"  OK  {name}")
        except ImportError:
            print(f"  SKIP {name} (optional)")

    # 4. Check server Tool registration
    print("\n[4/4] Checking MCP Tool registration...")
    try:
        from bioopenclaw.mcp_servers.data_agent.server import TOOLS, TOOL_HANDLERS
        registered_tools = [t.name for t in TOOLS]
        print(f"  Registered tools ({len(registered_tools)}):")
        for t in registered_tools:
            handler_ok = t in TOOL_HANDLERS
            print(f"    {'OK' if handler_ok else 'FAIL'}  {t}")
            if not handler_ok:
                errors.append(f"Tool '{t}' registered but no handler")
    except Exception as e:
        errors.append(f"Server registration: {e}")
        print(f"  FAIL: {e}")

    # Summary
    print("\n" + "=" * 60)
    if errors:
        print(f"RESULT: {len(errors)} error(s) found")
        for err in errors:
            print(f"  - {err}")
        return False
    else:
        print("RESULT: All checks passed!")
        print("\nTo start the server:")
        print("  python -m bioopenclaw.mcp_servers.data_agent.server")
        print("  # or")
        print("  data-agent-server")
        return True


def main() -> None:
    success = asyncio.run(verify_tools())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
