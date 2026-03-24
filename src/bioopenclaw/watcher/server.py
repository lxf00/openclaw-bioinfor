"""Watcher MCP Server — exposes monitoring and steering tools via MCP.

Start via CLI::

    python -m bioopenclaw.watcher.server
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from bioopenclaw.watcher.config import get_config
from bioopenclaw.watcher.detector import WatcherDetector
from bioopenclaw.watcher.models import (
    CorrectionRecord,
    DetectionResult,
    Priority,
    TriggerType,
)
from bioopenclaw.watcher.steering import SteeringQueue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

cfg = get_config()
server = Server(cfg.server_name)

detector = WatcherDetector(cfg)
steering_queue = SteeringQueue()

AGENT_NAMES = ["scout_agent", "data_agent", "model_agent", "research_agent"]

# ── Tool implementations ──────────────────────────────────────────────────


async def check_agent_status(
    agent_name: str | None = None,
) -> dict[str, Any]:
    """Read agents' active_context.md to assess their current status."""
    agents_dir = Path(cfg.agents_dir)
    targets = [agent_name] if agent_name else AGENT_NAMES

    statuses: dict[str, Any] = {}
    for name in targets:
        ctx_file = agents_dir / name / "active_context.md"
        if not ctx_file.exists():
            statuses[name] = {"status": "no_context_file", "file": str(ctx_file)}
            continue
        try:
            content = ctx_file.read_text(encoding="utf-8")
            sections: dict[str, str] = {}
            current_section = ""
            for line in content.split("\n"):
                if line.startswith("## "):
                    current_section = line[3:].strip()
                    sections[current_section] = ""
                elif current_section:
                    sections[current_section] += line + "\n"

            blocked = sections.get("Blocked", "").strip()
            statuses[name] = {
                "status": "blocked" if blocked and blocked != "（暂无）" else "active",
                "current_focus": sections.get("Current Focus", "").strip()[:200],
                "blocked": blocked[:200] if blocked else "",
                "next_steps": sections.get("Next Steps", "").strip()[:200],
            }
        except Exception as e:
            statuses[name] = {"status": "error", "error": str(e)}

    return {"success": True, "agent_statuses": statuses}


async def send_steering_message(
    target_agent: str,
    message: str,
    priority: str = "medium",
    trigger_type: str = "loop_detection",
) -> dict[str, Any]:
    """Write a steering message to shared_memory/inbox/."""
    try:
        filepath = steering_queue.write_inbox_message(
            target_agent=target_agent,
            message=message,
            priority=priority,
            trigger_type=trigger_type,
        )

        normalized_trigger = _normalize_trigger_type(trigger_type)
        record = CorrectionRecord(
            target_agent=target_agent,
            trigger_type=normalized_trigger,
            trigger_details=f"Manual steering: {trigger_type}",
            action=f"注入 steering 消息：「{message[:100]}」",
            priority=Priority(priority),
        )
        log_path = steering_queue.log_correction(record)

        return {
            "success": True,
            "inbox_file": str(filepath),
            "correction_log": str(log_path),
            "target_agent": target_agent,
            "priority": priority,
        }
    except Exception as e:
        logger.error("Failed to send steering message: %s", e)
        return {"success": False, "error": str(e)}


async def run_detection_check(
    tool_calls: list[dict[str, Any]] | None = None,
    outputs: list[str] | None = None,
    agent_name: str = "",
) -> dict[str, Any]:
    """Run the Watcher detector on provided tool call / output history."""
    det = WatcherDetector(cfg)
    detections: list[dict[str, Any]] = []

    if tool_calls:
        for call in tool_calls:
            result = det.record_tool_call(
                tool_name=call.get("tool_name", ""),
                params=call.get("params", {}),
                agent_name=agent_name,
            )
            if result:
                detections.append(result.model_dump(mode="json"))

    if outputs:
        for output in outputs:
            result = det.record_output(output, agent_name=agent_name)
            if result:
                detections.append(result.model_dump(mode="json"))

    return {
        "success": True,
        "detections_found": len(detections),
        "detections": detections,
        "total_tool_calls_checked": len(tool_calls) if tool_calls else 0,
        "total_outputs_checked": len(outputs) if outputs else 0,
    }


# ── Tool registry ──────────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="check_agent_status",
        description=(
            "读取各 Agent 的 active_context.md，获取当前状态。"
            "可指定单个 Agent 或检查所有 Agent。"
            "返回每个 Agent 的 Current Focus、Blocked 状态、Next Steps。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Agent 名称（如 'data_agent'），留空则检查所有 Agent",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="send_steering_message",
        description=(
            "向指定 Agent 发送纠偏消息。"
            "消息写入 shared_memory/inbox/，同时记录到 corrections_log。"
            "用于检测到异常后引导 Agent 改变行为方向。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "target_agent": {
                    "type": "string",
                    "description": "目标 Agent 名称（如 'data_agent'）",
                },
                "message": {
                    "type": "string",
                    "description": "纠偏消息内容（说明问题 + 建议方向）",
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "优先级（默认 medium）",
                    "default": "medium",
                },
                "trigger_type": {
                    "type": "string",
                    "enum": [
                        "loop_detection",
                        "stagnation",
                        "memory_quality",
                        "repeated_tool_call",
                        "max_rounds_exceeded",
                        "output_stagnation",
                        "blocked_stale",
                    ],
                    "description": "触发类型",
                    "default": "loop_detection",
                },
            },
            "required": ["target_agent", "message"],
        },
    ),
    Tool(
        name="run_detection_check",
        description=(
            "对提供的工具调用历史和/或输出历史运行 Watcher 检测器。"
            "检测重复工具调用（Level 1）和输出停滞（Level 2）。"
            "返回所有检测到的异常列表。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tool_calls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool_name": {"type": "string"},
                            "params": {"type": "object"},
                        },
                    },
                    "description": "工具调用历史 [{tool_name, params}]",
                },
                "outputs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Agent 输出文本历史",
                },
                "agent_name": {
                    "type": "string",
                    "description": "被检测的 Agent 名称",
                },
            },
            "required": [],
        },
    ),
]

TOOL_HANDLERS: dict[str, Any] = {
    "check_agent_status": check_agent_status,
    "send_steering_message": send_steering_message,
    "run_detection_check": run_detection_check,
}


def _normalize_trigger_type(trigger_type: str) -> TriggerType:
    """Normalize API-friendly trigger aliases to internal TriggerType enum."""
    alias_map = {
        "loop_detection": TriggerType.REPEATED_TOOL_CALL,
        "stagnation": TriggerType.OUTPUT_STAGNATION,
        "memory_quality": TriggerType.MEMORY_QUALITY,
        "repeated_tool_call": TriggerType.REPEATED_TOOL_CALL,
        "max_rounds_exceeded": TriggerType.MAX_ROUNDS_EXCEEDED,
        "output_stagnation": TriggerType.OUTPUT_STAGNATION,
        "blocked_stale": TriggerType.BLOCKED_STALE,
    }
    return alias_map.get(trigger_type, TriggerType.REPEATED_TOOL_CALL)


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
    logger.info("Watcher MCP Server starting...")
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
