"""Start all BioOpenClaw MCP servers.

Usage::

    python scripts/start_all_servers.py [--only data scout] [--list]

Each server runs as a subprocess. Press Ctrl+C to stop all servers.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SERVERS = {
    "data": {
        "module": "bioopenclaw.mcp_servers.data_agent.server",
        "port": 8001,
        "description": "Data Agent — data acquisition, QC, normalization",
    },
    "model": {
        "module": "bioopenclaw.mcp_servers.model_agent.server",
        "port": 8002,
        "description": "Model Agent — LoRA/QLoRA fine-tuning, model management",
    },
    "research": {
        "module": "bioopenclaw.mcp_servers.research_agent.server",
        "port": 8003,
        "description": "Research Agent — literature search, statistics, hypotheses",
    },
    "scout": {
        "module": "bioopenclaw.mcp_servers.scout_agent.server",
        "port": 8004,
        "description": "Scout Agent — HuggingFace/arXiv monitoring, model registry",
    },
    "watcher": {
        "module": "bioopenclaw.watcher.server",
        "port": 8005,
        "description": "Watcher — loop detection, steering, system monitoring",
    },
}


def start_servers(only: list[str] | None = None) -> dict[str, subprocess.Popen]:
    """Start MCP servers as subprocesses."""
    targets = only or list(SERVERS.keys())
    processes: dict[str, subprocess.Popen] = {}

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    for name in targets:
        if name not in SERVERS:
            print(f"[WARN] Unknown server: {name}, skipping")
            continue

        info = SERVERS[name]
        cmd = [sys.executable, "-m", info["module"]]

        print(f"[START] {name} (port {info['port']}): {info['description']}")

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes[name] = proc
            print(f"  PID: {proc.pid}")
        except Exception as e:
            print(f"  [ERROR] Failed to start {name}: {e}")

    return processes


def stop_all(processes: dict[str, subprocess.Popen]) -> None:
    """Gracefully stop all running server processes."""
    print("\n[STOP] Stopping all servers...")
    for name, proc in processes.items():
        if proc.poll() is None:
            print(f"  Stopping {name} (PID {proc.pid})...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            print(f"  {name} stopped")
        else:
            print(f"  {name} already exited (code {proc.returncode})")


def list_servers() -> None:
    """Print available servers."""
    print("Available MCP Servers:\n")
    print(f"{'Name':<12} {'Port':<8} {'Module':<50} Description")
    print("-" * 100)
    for name, info in SERVERS.items():
        print(f"{name:<12} {info['port']:<8} {info['module']:<50} {info['description']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Start BioOpenClaw MCP servers")
    parser.add_argument("--only", nargs="+", help="Start only specific servers")
    parser.add_argument("--list", action="store_true", help="List available servers")
    args = parser.parse_args()

    if args.list:
        list_servers()
        return

    processes = start_servers(args.only)

    if not processes:
        print("[ERROR] No servers started")
        sys.exit(1)

    print(f"\n[INFO] {len(processes)} server(s) running. Press Ctrl+C to stop.\n")

    def signal_handler(sig, frame):
        stop_all(processes)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            for name, proc in list(processes.items()):
                if proc.poll() is not None:
                    print(f"[WARN] {name} exited unexpectedly (code {proc.returncode})")
                    stderr = proc.stderr.read().decode() if proc.stderr else ""
                    if stderr:
                        print(f"  stderr: {stderr[:500]}")
                    del processes[name]

            if not processes:
                print("[ERROR] All servers have exited")
                sys.exit(1)

            time.sleep(5)
    except KeyboardInterrupt:
        stop_all(processes)


if __name__ == "__main__":
    main()
