"""Inbox dispatch — scans shared_memory/inbox/ and routes messages to target agents.

Usage::

    python scripts/inbox_dispatch.py [--dry-run] [--verbose]
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("inbox_dispatch")


def parse_yaml_front_matter(content: str) -> dict[str, str]:
    """Extract YAML front matter from a Markdown file."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    front_matter: dict[str, str] = {}
    for line in match.group(1).strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            front_matter[key.strip()] = value.strip()
    return front_matter


def dispatch_messages(inbox_dir: Path, agents_dir: Path, dry_run: bool = False) -> dict:
    """Scan inbox, parse messages, route to target agents, archive processed."""
    archive_dir = inbox_dir / "archive"

    if not inbox_dir.exists():
        logger.info("Inbox directory does not exist: %s", inbox_dir)
        return {"processed": 0, "errors": 0, "skipped": 0}

    messages = sorted(inbox_dir.glob("*.md"))
    if not messages:
        logger.info("No messages in inbox")
        return {"processed": 0, "errors": 0, "skipped": 0}

    processed = 0
    errors = 0
    skipped = 0
    dispatched: list[dict] = []

    for msg_file in messages:
        try:
            content = msg_file.read_text(encoding="utf-8")
            meta = parse_yaml_front_matter(content)

            if not meta:
                logger.warning("No front matter in %s, skipping", msg_file.name)
                skipped += 1
                continue

            target = meta.get("to", "")
            sender = meta.get("from", "unknown")
            priority = meta.get("priority", "medium")
            msg_type = meta.get("type", "unknown")

            if not target:
                logger.warning("No 'to' field in %s, skipping", msg_file.name)
                skipped += 1
                continue

            target_ctx = agents_dir / target / "active_context.md"
            if not target_ctx.exists():
                logger.warning(
                    "Target agent '%s' active_context.md not found: %s",
                    target, target_ctx,
                )
                skipped += 1
                continue

            logger.info(
                "Dispatching: %s → %s (from=%s, priority=%s, type=%s)",
                msg_file.name, target, sender, priority, msg_type,
            )

            if not dry_run:
                _append_to_context(target_ctx, msg_file.name, sender, priority, msg_type, content)

                archive_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(msg_file), str(archive_dir / msg_file.name))

            dispatched.append({
                "file": msg_file.name,
                "from": sender,
                "to": target,
                "priority": priority,
                "type": msg_type,
            })
            processed += 1

        except Exception as e:
            logger.error("Error processing %s: %s", msg_file.name, e)
            errors += 1

    report = {
        "processed": processed,
        "errors": errors,
        "skipped": skipped,
        "dispatched": dispatched,
        "dry_run": dry_run,
    }

    logger.info(
        "Dispatch complete: %d processed, %d errors, %d skipped",
        processed, errors, skipped,
    )
    return report


def _append_to_context(
    ctx_file: Path,
    filename: str,
    sender: str,
    priority: str,
    msg_type: str,
    content: str,
) -> None:
    """Append an incoming message reference to an agent's active_context.md."""
    ctx_content = ctx_file.read_text(encoding="utf-8")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n### [{now}] Message from {sender}\n"
        f"- **Priority**: {priority}\n"
        f"- **Type**: {msg_type}\n"
        f"- **Source file**: `{filename}` (archived)\n"
    )

    body_match = re.search(r"^---\s*\n.*?\n---\s*\n(.+)", content, re.DOTALL)
    if body_match:
        body_preview = body_match.group(1).strip()[:200]
        entry += f"- **Preview**: {body_preview}\n"

    if "## Recent Decisions" in ctx_content:
        ctx_content = ctx_content.replace(
            "## Recent Decisions",
            f"## Incoming Messages\n{entry}\n---\n\n## Recent Decisions",
        )
    else:
        ctx_content += f"\n\n## Incoming Messages\n{entry}\n"

    ctx_file.write_text(ctx_content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch inbox messages to target agents")
    parser.add_argument("--dry-run", action="store_true", help="Preview without moving files")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--inbox-dir",
        type=Path,
        default=PROJECT_ROOT / "shared_memory" / "inbox",
        help="Inbox directory path",
    )
    parser.add_argument(
        "--agents-dir",
        type=Path,
        default=PROJECT_ROOT / "agents",
        help="Agents directory path",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    report = dispatch_messages(args.inbox_dir, args.agents_dir, args.dry_run)

    import json
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
