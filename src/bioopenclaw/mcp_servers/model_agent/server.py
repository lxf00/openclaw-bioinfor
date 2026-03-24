"""Model Agent MCP Server — exposes fine-tuning and model management tools via MCP.

Start via CLI::

    python -m bioopenclaw.mcp_servers.model_agent.server
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from bioopenclaw.mcp_servers.model_agent.config import get_config
from bioopenclaw.mcp_servers.model_agent.tools.lora_config import create_lora_config
from bioopenclaw.mcp_servers.model_agent.tools.model_download import download_model
from bioopenclaw.mcp_servers.model_agent.tools.training_monitor import check_training_status

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
        name="create_lora_config",
        description=(
            "生成 LoRA/QLoRA 微调配置。"
            "包含 PEFT 配置（rank, alpha, target_modules）和训练参数。"
            "内置 scGPT/ESM2/Geneformer 的推荐参数。"
            "可选输出为 JSON 配置文件。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "base_model": {
                    "type": "string",
                    "description": "基础模型名称或 HuggingFace ID",
                },
                "task_type": {
                    "type": "string",
                    "description": "任务类型（如 'classification', 'regression'）",
                    "default": "classification",
                },
                "method": {
                    "type": "string",
                    "enum": ["lora", "qlora"],
                    "description": "微调方法（默认 lora）",
                    "default": "lora",
                },
                "rank": {"type": "integer", "description": "LoRA rank（可选，使用推荐值）"},
                "alpha": {"type": "integer", "description": "LoRA alpha（可选，使用推荐值）"},
                "learning_rate": {"type": "number", "description": "学习率（可选，使用推荐值）"},
                "epochs": {"type": "integer", "description": "训练轮数（默认 10）"},
                "batch_size": {"type": "integer", "description": "批量大小（默认 8）"},
                "target_modules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "LoRA 目标模块（可选，使用推荐值）",
                },
                "quantization_bits": {
                    "type": "integer",
                    "enum": [4, 8],
                    "description": "量化位数（仅 QLoRA，默认 4）",
                },
                "output_path": {
                    "type": "string",
                    "description": "输出配置文件路径（可选）",
                },
            },
            "required": ["base_model"],
        },
    ),
    Tool(
        name="download_model",
        description=(
            "从 HuggingFace Hub 下载模型权重。"
            "使用 snapshot_download 支持断点续传。"
            "可指定版本和文件过滤模式。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "HuggingFace 模型 ID（如 'facebook/esm2_t33_650M_UR50D'）",
                },
                "output_dir": {
                    "type": "string",
                    "description": "下载目录（默认 models/<model_id>/）",
                },
                "revision": {
                    "type": "string",
                    "description": "模型版本/分支（默认 main）",
                    "default": "main",
                },
                "allow_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "允许的文件模式（如 ['*.bin', '*.json']）",
                },
                "ignore_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "忽略的文件模式",
                },
            },
            "required": ["model_id"],
        },
    ),
    Tool(
        name="check_training_status",
        description=(
            "检查训练任务的状态。"
            "读取 HuggingFace Trainer 的 checkpoint 目录和 trainer_state.json。"
            "返回训练进度、损失曲线、最佳 checkpoint 等信息。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "项目名称（在 checkpoints 目录下的子目录）",
                },
                "checkpoint_dir": {
                    "type": "string",
                    "description": "checkpoint 目录路径（默认使用配置中的 checkpoints_dir）",
                },
            },
            "required": [],
        },
    ),
]

TOOL_HANDLERS: dict[str, Any] = {
    "create_lora_config": create_lora_config,
    "download_model": download_model,
    "check_training_status": check_training_status,
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
    logger.info("Model Agent MCP Server starting...")
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
