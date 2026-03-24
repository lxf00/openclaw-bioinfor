"""Scout Agent MCP Server — exposes model monitoring tools via MCP.

Start via CLI::

    python -m bioopenclaw.mcp_servers.scout_agent.server

Or via the registered entry point::

    scout-agent-server
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from bioopenclaw.mcp_servers.scout_agent.config import get_config
from bioopenclaw.mcp_servers.scout_agent.tools.arxiv_monitor import scan_arxiv_papers
from bioopenclaw.mcp_servers.scout_agent.tools.hf_monitor import scan_huggingface_models
from bioopenclaw.mcp_servers.scout_agent.tools.registry_writer import register_model

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
        name="scan_huggingface_models",
        description=(
            "扫描 HuggingFace Hub 上最近发布/更新的生物信息学模型。"
            "按标签和作者过滤，返回模型 ID、下载量、点赞数等元数据。"
            "用于定期监控生物基础模型动态。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "搜索标签（如 ['biology', 'single-cell', 'protein']）",
                },
                "authors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "关注的作者/组织（如 ['facebook', 'bowang-lab']）",
                },
                "days_back": {
                    "type": "integer",
                    "description": "搜索最近 N 天发布/更新的模型（默认 7）",
                    "default": 7,
                },
                "limit": {
                    "type": "integer",
                    "description": "最大返回模型数（默认 50）",
                    "default": 50,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="scan_arxiv_papers",
        description=(
            "搜索 arXiv 上最近的生物信息学预印本。"
            "默认搜索 q-bio.GN、q-bio.QM、q-bio.BM、cs.LG 类别。"
            "可用自定义查询词进一步过滤。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词（可选，如 'single cell foundation model'）",
                },
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "arXiv 类别（默认 ['q-bio.GN', 'q-bio.QM', 'q-bio.BM', 'cs.LG']）",
                },
                "days_back": {
                    "type": "integer",
                    "description": "搜索最近 N 天的论文（默认 7）",
                    "default": 7,
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回数（默认 30）",
                    "default": 30,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="register_model",
        description=(
            "将模型注册到 shared_memory/model_registry。"
            "生成标准格式的模型 Markdown 文件并更新索引。"
            "如果模型已存在，将更新其信息。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "HuggingFace 模型 ID（如 'facebook/esm2_t33_650M_UR50D'）",
                },
                "name": {
                    "type": "string",
                    "description": "显示名称（如 'ESM2-650M'）",
                },
                "version": {"type": "string", "description": "版本号"},
                "model_type": {
                    "type": "string",
                    "description": "模型类型（如 '蛋白质语言模型'、'单细胞基础模型'）",
                },
                "parameters": {
                    "type": "string",
                    "description": "参数量（如 '650M'、'7B'）",
                },
                "license": {"type": "string", "description": "许可证"},
                "architecture": {
                    "type": "string",
                    "description": "模型架构（如 'Transformer'、'GNN'）",
                },
                "modalities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "输入模态（如 ['protein sequence', 'gene expression']）",
                },
                "species": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "适用物种",
                },
                "paper_url": {"type": "string", "description": "论文 URL（DOI 或 arXiv）"},
                "benchmarks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "benchmark": {"type": "string"},
                            "task": {"type": "string"},
                            "score": {"type": "string"},
                            "date": {"type": "string"},
                        },
                    },
                    "description": "基准测试结果",
                },
                "limitations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "已知限制",
                },
                "description": {
                    "type": "string",
                    "description": "模型描述（一段话）",
                },
            },
            "required": ["model_id", "name"],
        },
    ),
]

TOOL_HANDLERS: dict[str, Any] = {
    "scan_huggingface_models": scan_huggingface_models,
    "scan_arxiv_papers": scan_arxiv_papers,
    "register_model": register_model,
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
    logger.info("Scout Agent MCP Server starting...")
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
