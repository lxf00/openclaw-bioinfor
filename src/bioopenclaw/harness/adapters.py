"""Concrete harness adapters backed by existing BioOpenClaw modules."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from bioopenclaw.harness.models import (
    AgentInvocation,
    AgentResult,
    AgentResultStatus,
    ArtifactKind,
    ArtifactRef,
    CorrectionAction,
    CorrectionProposal,
    GovernanceOutcome,
    ToolCallRecord,
    ToolCallStatus,
    TriggerSeverity,
    TriggerType,
    WatcherTrigger,
)
from bioopenclaw.watcher.detector import WatcherDetector

AGENT_SERVER_MODULES: dict[str, str] = {
    "data_agent": "bioopenclaw.mcp_servers.data_agent.server",
    "scout_agent": "bioopenclaw.mcp_servers.scout_agent.server",
    "model_agent": "bioopenclaw.mcp_servers.model_agent.server",
    "research_agent": "bioopenclaw.mcp_servers.research_agent.server",
}


class ExistingServerAgentGateway:
    """Invoke existing agent tool handlers directly inside the Python process."""

    def __init__(
        self,
        tool_selection: dict[str, dict[str, Any]] | None = None,
        transport: str = "direct",
        mcp_config_path: str | Path | None = None,
        repo_root: str | Path | None = None,
        data_root: str | Path | None = None,
    ) -> None:
        self.tool_selection = tool_selection or {}
        self.transport = transport
        self.repo_root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
        self.data_root = Path(data_root) if data_root else self.repo_root
        self.mcp_config_path = (
            Path(mcp_config_path)
            if mcp_config_path
            else self.repo_root / "mcp_config.json"
        )

    async def invoke(self, invocation: AgentInvocation) -> AgentResult:
        selection = self.tool_selection.get(invocation.target_agent, {})
        tool_name = (
            invocation.constraints.get("tool_name")
            or selection.get("tool_name")
        )
        tool_args = {
            **selection.get("tool_args", {}),
            **invocation.constraints.get("tool_args", {}),
        }

        if not tool_name:
            return AgentResult(
                invocation_id=invocation.invocation_id,
                status=AgentResultStatus.BLOCKED,
                summary=(
                    f"No tool mapping configured for {invocation.target_agent}. "
                    "Provide constraints.tool_name/tool_args or gateway defaults."
                ),
            )

        module_path = AGENT_SERVER_MODULES.get(invocation.target_agent)
        if not module_path:
            return AgentResult(
                invocation_id=invocation.invocation_id,
                status=AgentResultStatus.FAILED,
                summary=f"Unknown target agent: {invocation.target_agent}",
            )

        if self.transport == "stdio":
            return await self._invoke_stdio(
                invocation=invocation,
                module_path=module_path,
                tool_name=tool_name,
                tool_args=tool_args,
            )

        module = importlib.import_module(module_path)
        handlers = getattr(module, "TOOL_HANDLERS")
        handler = handlers.get(tool_name)
        if handler is None:
            return AgentResult(
                invocation_id=invocation.invocation_id,
                status=AgentResultStatus.FAILED,
                summary=f"Tool '{tool_name}' is not registered for {invocation.target_agent}",
            )

        tool_record = ToolCallRecord(
            run_id=invocation.run_id,
            stage_id=invocation.stage_id,
            agent=invocation.target_agent,
            server_name=module_path,
            tool_name=tool_name,
            arguments=tool_args,
            status=ToolCallStatus.SUCCESS,
        )
        try:
            result = await handler(**tool_args)
        except Exception as exc:
            tool_record.status = ToolCallStatus.ERROR
            tool_record.error_type = exc.__class__.__name__
            tool_record.response_summary = str(exc)
            return AgentResult(
                invocation_id=invocation.invocation_id,
                status=AgentResultStatus.FAILED,
                summary=f"{invocation.target_agent}.{tool_name} failed: {exc}",
                tool_calls=[tool_record],
            )

        success = bool(result.get("success", True))
        tool_record.response_summary = _summarize_result(result)
        artifact = ArtifactRef(
            run_id=invocation.run_id,
            kind=ArtifactKind.REPORT,
            name=f"{invocation.target_agent}_{tool_name}_result",
            uri=f"harness://{invocation.run_id}/{invocation.stage_id}/{tool_name}",
            producer_agent=invocation.target_agent,
            stage_id=invocation.stage_id,
            metadata={"tool_name": tool_name, "result": result},
        )
        return AgentResult(
            invocation_id=invocation.invocation_id,
            status=AgentResultStatus.SUCCESS if success else AgentResultStatus.FAILED,
            summary=tool_record.response_summary,
            outputs=result,
            artifacts=[artifact] if success else [],
            tool_calls=[tool_record],
        )

    async def _invoke_stdio(
        self,
        invocation: AgentInvocation,
        module_path: str,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> AgentResult:
        tool_record = ToolCallRecord(
            run_id=invocation.run_id,
            stage_id=invocation.stage_id,
            agent=invocation.target_agent,
            server_name=module_path,
            tool_name=tool_name,
            arguments=tool_args,
            status=ToolCallStatus.SUCCESS,
        )

        try:
            params = self._build_stdio_params(invocation.target_agent)
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    available = await session.list_tools()
                    tool_names = {tool.name for tool in available.tools}
                    if tool_name not in tool_names:
                        raise RuntimeError(
                            f"Tool '{tool_name}' not exposed by MCP server "
                            f"{invocation.target_agent}: {sorted(tool_names)}"
                        )
                    response = await session.call_tool(tool_name, tool_args)
        except Exception as exc:
            tool_record.status = ToolCallStatus.TRANSPORT_ERROR
            tool_record.error_type = exc.__class__.__name__
            tool_record.response_summary = str(exc)
            return AgentResult(
                invocation_id=invocation.invocation_id,
                status=AgentResultStatus.FAILED,
                summary=f"stdio MCP call failed for {invocation.target_agent}.{tool_name}: {exc}",
                tool_calls=[tool_record],
            )

        result = self._parse_call_tool_result(response)
        success = bool(result.get("success", True))
        tool_record.response_summary = _summarize_result(result)
        artifact = ArtifactRef(
            run_id=invocation.run_id,
            kind=ArtifactKind.REPORT,
            name=f"{invocation.target_agent}_{tool_name}_result",
            uri=f"mcp://{invocation.target_agent}/{tool_name}",
            producer_agent=invocation.target_agent,
            stage_id=invocation.stage_id,
            metadata={"tool_name": tool_name, "result": result, "transport": "stdio"},
        )
        return AgentResult(
            invocation_id=invocation.invocation_id,
            status=AgentResultStatus.SUCCESS if success else AgentResultStatus.FAILED,
            summary=tool_record.response_summary,
            outputs=result,
            artifacts=[artifact] if success else [],
            tool_calls=[tool_record],
        )

    def _build_stdio_params(self, agent_name: str) -> StdioServerParameters:
        config = json.loads(self.mcp_config_path.read_text(encoding="utf-8"))
        server_key = agent_name.replace("_", "-")
        server_cfg = config["mcpServers"][server_key]
        env = dict(os.environ)
        env.update({
            key: self._replace_placeholders(value)
            for key, value in server_cfg.get("env", {}).items()
        })
        return StdioServerParameters(
            command=self._replace_placeholders(server_cfg["command"]),
            args=[self._replace_placeholders(arg) for arg in server_cfg.get("args", [])],
            env=env,
            cwd=self._replace_placeholders(server_cfg.get("cwd") or str(self.repo_root)),
        )

    def _replace_placeholders(self, value: str) -> str:
        return (
            value.replace("__VENV_PY__", sys.executable)
            .replace("__REPO_ROOT__", str(self.repo_root))
            .replace("__DATA_ROOT__", str(self.data_root))
        )

    @staticmethod
    def _parse_call_tool_result(response: Any) -> dict[str, Any]:
        for item in getattr(response, "content", []):
            text = getattr(item, "text", None)
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"success": True, "message": text}
        return {"success": False, "error": "No textual result returned by MCP server"}


class WatcherDetectorGateway:
    """Translate existing watcher detector signals into harness governance objects."""

    def __init__(self, detector: WatcherDetector | None = None) -> None:
        self.detector = detector or WatcherDetector()

    async def assess(
        self,
        run_id: str,
        recent_tool_calls: list[ToolCallRecord],
        recent_outputs: list[str],
    ) -> GovernanceOutcome:
        outcome = GovernanceOutcome()

        for call in recent_tool_calls:
            detection = self.detector.record_tool_call(
                tool_name=call.tool_name,
                params=call.arguments,
                agent_name=call.agent,
            )
            if detection:
                trigger = self._to_trigger(run_id, detection)
                proposal = self._to_proposal(run_id, trigger)
                outcome.triggers.append(trigger)
                outcome.proposals.append(proposal)

        for output in recent_outputs:
            detection = self.detector.record_output(output)
            if detection:
                trigger = self._to_trigger(run_id, detection)
                proposal = self._to_proposal(run_id, trigger)
                outcome.triggers.append(trigger)
                outcome.proposals.append(proposal)

        if outcome.triggers:
            outcome.health = "risky"

        return outcome

    def _to_trigger(self, run_id: str, detection: Any) -> WatcherTrigger:
        trigger_type = TriggerType.REPEATED_TOOL_CALL
        if detection.trigger_type.value == "max_rounds_exceeded":
            trigger_type = TriggerType.EXCESSIVE_RETRY
        elif detection.trigger_type.value == "output_stagnation":
            trigger_type = TriggerType.NO_PROGRESS

        severity = TriggerSeverity.MEDIUM if detection.level < 3 else TriggerSeverity.LOW
        if detection.level == 1:
            severity = TriggerSeverity.HIGH

        return WatcherTrigger(
            run_id=run_id,
            trigger_type=trigger_type,
            severity=severity,
            description=detection.message,
            evidence_refs=[detection.trigger_type.value],
        )

    def _to_proposal(self, run_id: str, trigger: WatcherTrigger) -> CorrectionProposal:
        action = CorrectionAction.REQUEST_VALIDATION
        if trigger.trigger_type == TriggerType.REPEATED_TOOL_CALL:
            action = CorrectionAction.NARROW_SCOPE
        elif trigger.trigger_type == TriggerType.EXCESSIVE_RETRY:
            action = CorrectionAction.ROLLBACK

        return CorrectionProposal(
            run_id=run_id,
            trigger_id=trigger.trigger_id,
            action=action,
            reason=trigger.description,
            confidence=0.75,
        )


def _summarize_result(result: dict[str, Any]) -> str:
    if "error" in result:
        return str(result["error"])
    if "message" in result:
        return str(result["message"])
    if "status" in result:
        return str(result["status"])
    keys = list(result.keys())[:4]
    return f"Tool call succeeded with keys: {', '.join(keys)}"
