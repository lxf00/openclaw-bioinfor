from __future__ import annotations

import pytest

from bioopenclaw.harness.adapters import ExistingServerAgentGateway, WatcherDetectorGateway
from bioopenclaw.harness.models import AgentInvocation, ToolCallRecord, ToolCallStatus


@pytest.mark.asyncio
async def test_existing_server_agent_gateway_invokes_research_handler() -> None:
    gateway = ExistingServerAgentGateway(
        tool_selection={
            "research_agent": {
                "tool_name": "generate_hypothesis",
                "tool_args": {
                    "background": "T cell activation changes after perturbation.",
                    "observation": "Activated cells express a higher marker score.",
                },
            }
        }
    )

    result = await gateway.invoke(
        AgentInvocation(
            run_id="run_test",
            stage_id="stage_hypothesis",
            target_agent="research_agent",
            objective="Generate a first-pass hypothesis.",
        )
    )

    assert result.status.value == "success"
    assert result.outputs["success"] is True
    assert result.tool_calls[0].tool_name == "generate_hypothesis"
    assert result.artifacts


@pytest.mark.asyncio
async def test_existing_server_agent_gateway_supports_stdio_mcp() -> None:
    gateway = ExistingServerAgentGateway(
        transport="stdio",
        tool_selection={
            "research_agent": {
                "tool_name": "generate_hypothesis",
                "tool_args": {
                    "background": "B cells change after perturbation.",
                    "observation": "Marker intensity rises after treatment.",
                },
            }
        },
    )

    result = await gateway.invoke(
        AgentInvocation(
            run_id="run_stdio",
            stage_id="stage_hypothesis",
            target_agent="research_agent",
            objective="Run a protocol-level hypothesis generation call.",
        )
    )

    assert result.status.value == "success"
    assert result.outputs["success"] is True
    assert result.artifacts[0].uri.startswith("mcp://")
    assert result.tool_calls[0].tool_name == "generate_hypothesis"


@pytest.mark.asyncio
async def test_watcher_detector_gateway_detects_repeated_tool_calls() -> None:
    gateway = WatcherDetectorGateway()
    calls = [
        ToolCallRecord(
            run_id="run_test",
            stage_id="stage_data",
            agent="data_agent",
            server_name="bioopenclaw.mcp_servers.data_agent.server",
            tool_name="inspect_dataset",
            arguments={"file_path": "demo.h5ad"},
            status=ToolCallStatus.SUCCESS,
        )
        for _ in range(3)
    ]

    outcome = await gateway.assess("run_test", recent_tool_calls=calls, recent_outputs=[])

    assert outcome.triggers
    assert outcome.proposals
    assert outcome.triggers[0].trigger_type.value == "repeated_tool_call"
    assert outcome.proposals[0].action.value == "narrow_scope"
