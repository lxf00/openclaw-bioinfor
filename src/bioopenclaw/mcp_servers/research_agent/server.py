"""Research Agent MCP Server — exposes literature, hypothesis, and stats tools via MCP.

Start via CLI::

    python -m bioopenclaw.mcp_servers.research_agent.server
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from bioopenclaw.mcp_servers.research_agent.config import get_config
from bioopenclaw.mcp_servers.research_agent.tools.hypothesis_gen import generate_hypothesis
from bioopenclaw.mcp_servers.research_agent.tools.literature_search import search_pubmed
from bioopenclaw.mcp_servers.research_agent.tools.statistical_test import run_statistical_test

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

cfg = get_config()
server = Server(cfg.server_name)

# ── Tool registry ──────────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="search_pubmed",
        description=(
            "通过 NCBI PubMed API 搜索生物医学文献。"
            "返回标题、作者、摘要、MeSH 术语和 PubMed 链接。"
            "支持日期范围过滤和排序方式选择。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "PubMed 搜索查询（支持布尔运算符，如 'scGPT AND single cell'）",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回数（默认 20）",
                    "default": 20,
                },
                "email": {
                    "type": "string",
                    "description": "NCBI 联系邮箱（可选，优先使用环境变量）",
                },
                "database": {
                    "type": "string",
                    "description": "数据库（默认 'pubmed'，也支持 'pmc'）",
                    "default": "pubmed",
                },
                "sort_by": {
                    "type": "string",
                    "description": "排序方式（默认 'relevance'）",
                    "enum": ["relevance", "pub_date", "first_author"],
                    "default": "relevance",
                },
                "date_from": {
                    "type": "string",
                    "description": "起始日期 YYYY（可选）",
                },
                "date_to": {
                    "type": "string",
                    "description": "结束日期 YYYY（可选）",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="generate_hypothesis",
        description=(
            "生成结构化的科学假设文档。"
            "包含背景、观察、H0/H1、检验方案、数据要求、文献支持。"
            "可选输出为 Markdown 文件。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "background": {
                    "type": "string",
                    "description": "假设的科学背景（基于哪些已知事实）",
                },
                "observation": {
                    "type": "string",
                    "description": "驱动假设的观察/发现",
                },
                "h0": {
                    "type": "string",
                    "description": "零假设 H0（可选，不填则生成模板）",
                },
                "h1": {
                    "type": "string",
                    "description": "备择假设 H1（可选）",
                },
                "suggested_test": {
                    "type": "string",
                    "description": "建议的统计检验方法",
                },
                "data_requirements": {
                    "type": "string",
                    "description": "数据要求描述",
                },
                "literature_refs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "支持性文献引用",
                },
                "output_path": {
                    "type": "string",
                    "description": "输出 Markdown 文件路径（可选）",
                },
            },
            "required": ["background", "observation"],
        },
    ),
    Tool(
        name="run_statistical_test",
        description=(
            "执行统计检验。支持 t_test、mann_whitney、wilcoxon、chi2、ks_test、shapiro。"
            "返回统计量、p 值、效应量。支持 Bonferroni 和 BH-FDR 多重检验校正。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "test_type": {
                    "type": "string",
                    "description": "检验类型",
                    "enum": ["t_test", "mann_whitney", "wilcoxon", "chi2", "ks_test", "shapiro"],
                },
                "group_a": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "组 A 数据",
                },
                "group_b": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "组 B 数据（部分检验必须提供）",
                },
                "alternative": {
                    "type": "string",
                    "enum": ["two-sided", "less", "greater"],
                    "description": "备择假设方向（默认 two-sided）",
                    "default": "two-sided",
                },
                "alpha": {
                    "type": "number",
                    "description": "显著性水平（默认 0.05）",
                    "default": 0.05,
                },
                "correction_method": {
                    "type": "string",
                    "enum": ["none", "bonferroni", "bh_fdr"],
                    "description": "多重检验校正方法（默认 none）",
                    "default": "none",
                },
                "paired": {
                    "type": "boolean",
                    "description": "是否为配对检验（仅 t_test）",
                    "default": False,
                },
            },
            "required": ["test_type", "group_a"],
        },
    ),
]

TOOL_HANDLERS: dict[str, Any] = {
    "search_pubmed": search_pubmed,
    "generate_hypothesis": generate_hypothesis,
    "run_statistical_test": run_statistical_test,
}


@server.list_tools()
async def handle_list_tools() -> ListToolsResult:
    return ListToolsResult(tools=TOOLS)


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    logger.info(
        "Tool call: %s | args: %s",
        name,
        json.dumps(arguments, ensure_ascii=False, default=str)[:300],
    )

    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        result = {"success": False, "error": f"Unknown tool: {name}"}
    else:
        result = await handler(**arguments)

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2, default=str),
            )
        ]
    )


async def _run() -> None:
    cfg.ensure_dirs()
    logger.info("Research Agent MCP Server starting...")
    logger.info("Available tools: %s", ", ".join(TOOL_HANDLERS.keys()))

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    import asyncio
    asyncio.run(_run())


if __name__ == "__main__":
    main()
