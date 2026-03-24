#!/usr/bin/env python3
"""Sync system prompt files to OpenClaw remote instance directories.

Usage:
    python scripts/sync_openclaw_prompts.py --openclaw-home /home/you/.openclaw
"""

from __future__ import annotations

import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_ROOT = PROJECT_ROOT / "openclaw_configs"

MAPPING = {
    "main": "main",
    "data_agent": "data",
    "scout_agent": "scout",
    "model_agent": "model",
    "research_agent": "research",
    "watcher": "watcher",
}


def sync_prompts(openclaw_home: Path, dry_run: bool = False) -> list[tuple[Path, Path]]:
    copied: list[tuple[Path, Path]] = []
    for config_name, agent_dir_name in MAPPING.items():
        src = PROMPTS_ROOT / config_name / "system_prompt.md"
        dst = openclaw_home / "agents" / agent_dir_name / "agent" / "system_prompt.md"
        if not src.exists():
            raise FileNotFoundError(f"Missing source prompt: {src}")
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append((src, dst))
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync OpenClaw system prompts")
    parser.add_argument("--openclaw-home", required=True, type=Path, help="OpenClaw root directory")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files")
    args = parser.parse_args()

    copied = sync_prompts(args.openclaw_home, dry_run=args.dry_run)
    mode = "DRY-RUN" if args.dry_run else "DONE"
    print(f"[{mode}] Prompt sync summary:")
    for src, dst in copied:
        print(f"  {src} -> {dst}")


if __name__ == "__main__":
    main()
