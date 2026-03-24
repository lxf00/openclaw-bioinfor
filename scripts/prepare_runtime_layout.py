#!/usr/bin/env python3
"""Prepare a shared runtime layout for remote BioOpenClaw deployment.

This script creates the server-side data directories and optionally maps the
repository's ``agents/`` and ``shared_memory/`` trees onto the runtime data
root so Harness, Watcher, and OpenClaw all observe the same state surface.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


RUNTIME_DIRS = [
    "data/raw",
    "data/processed",
    "data/reports",
    "data/lineage",
    "models/checkpoints",
    "models/configs",
    "shared_memory/model_registry",
    "shared_memory/literature",
    "shared_memory/experiments",
    "shared_memory/inbox/archive",
    "agents/scout_agent/daily_log",
    "agents/data_agent/daily_log",
    "agents/model_agent/daily_log",
    "agents/research_agent/daily_log",
    "agents/watcher/daily_log",
    "agents/watcher/corrections_log",
]


def ensure_runtime_dirs(data_root: Path) -> list[Path]:
    """Create all required runtime directories under *data_root*."""
    created: list[Path] = []
    for relative in RUNTIME_DIRS:
        target = data_root / relative
        target.mkdir(parents=True, exist_ok=True)
        created.append(target)
    return created


def map_state_surface(repo_root: Path, data_root: Path, mode: str = "symlink") -> list[str]:
    """Expose a single shared state view for ``agents`` and ``shared_memory``.

    ``mode`` can be:
    - ``symlink``: replace the repo trees with symlinks into ``data_root``
    - ``copy``: copy the data trees into the repo if direct links are undesired
    - ``none``: leave the repo trees untouched
    """
    actions: list[str] = []
    for name in ("agents", "shared_memory"):
        repo_path = repo_root / name
        data_path = data_root / name
        data_path.mkdir(parents=True, exist_ok=True)

        if mode == "none":
            actions.append(f"left {repo_path} unchanged")
            continue

        if mode == "copy":
            if repo_path.exists() and not repo_path.is_symlink():
                shutil.copytree(repo_path, data_path, dirs_exist_ok=True)
                actions.append(f"copied {repo_path} -> {data_path}")
            elif not repo_path.exists():
                repo_path.mkdir(parents=True, exist_ok=True)
                shutil.copytree(repo_path, data_path, dirs_exist_ok=True)
                actions.append(f"initialized empty {data_path}")
            continue

        # symlink mode
        if repo_path.is_symlink():
            current_target = repo_path.resolve(strict=False)
            if current_target == data_path.resolve():
                actions.append(f"kept existing symlink {repo_path} -> {data_path}")
                continue
            repo_path.unlink()
            actions.append(f"removed stale symlink {repo_path}")
        elif repo_path.exists():
            backup = repo_root / f"{name}.bak"
            if backup.exists():
                if backup.is_dir():
                    shutil.rmtree(backup)
                else:
                    backup.unlink()
            repo_path.rename(backup)
            actions.append(f"backed up {repo_path} -> {backup}")

        repo_path.symlink_to(data_path, target_is_directory=True)
        actions.append(f"linked {repo_path} -> {data_path}")

    return actions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare remote BioOpenClaw runtime layout")
    parser.add_argument("--repo-root", type=Path, required=True, help="Repository root on the server")
    parser.add_argument("--data-root", type=Path, required=True, help="Shared runtime data root")
    parser.add_argument(
        "--state-mode",
        choices=["symlink", "copy", "none"],
        default="symlink",
        help="How to expose DATA_ROOT/{agents,shared_memory} to the repo",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    created = ensure_runtime_dirs(args.data_root)
    actions = map_state_surface(args.repo_root, args.data_root, mode=args.state_mode)

    print("Created/checked runtime directories:")
    for path in created:
        print(f"  - {path}")
    print("State surface actions:")
    for action in actions:
        print(f"  - {action}")


if __name__ == "__main__":
    main()
