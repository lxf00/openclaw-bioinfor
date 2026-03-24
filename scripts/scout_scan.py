"""Scout scan automation — scans HuggingFace, registers new models, checks consistency.

Usage::

    python scripts/scout_scan.py [--tags biology single-cell] [--days 7] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scout_scan")


async def run_scan(
    tags: list[str],
    authors: list[str],
    days_back: int,
    limit: int,
    dry_run: bool,
) -> dict:
    """Run the full Scout scan pipeline."""
    from bioopenclaw.mcp_servers.scout_agent.tools.hf_monitor import scan_huggingface_models
    from bioopenclaw.mcp_servers.scout_agent.tools.registry_writer import register_model

    logger.info("Starting HuggingFace scan (tags=%s, days_back=%d)", tags, days_back)
    scan_result = await scan_huggingface_models(
        tags=tags,
        authors=authors,
        days_back=days_back,
        limit=limit,
    )

    if not scan_result.get("success"):
        logger.error("Scan failed: %s", scan_result.get("error"))
        return scan_result

    models = scan_result.get("models", [])
    logger.info("Found %d models", len(models))

    registry_dir = PROJECT_ROOT / "shared_memory" / "model_registry"
    existing_files = {f.stem.lower() for f in registry_dir.glob("*.md") if f.name != "_index.md"}

    new_count = 0
    skip_count = 0
    registered = []

    for m in models:
        model_id = m.get("model_id", "")
        safe_name = model_id.replace("/", "_").replace("-", "_").lower()

        if safe_name in existing_files:
            skip_count += 1
            continue

        if dry_run:
            logger.info("[DRY RUN] Would register: %s", model_id)
            new_count += 1
            continue

        result = await register_model(
            model_id=model_id,
            name=model_id.split("/")[-1] if "/" in model_id else model_id,
            model_type="bioinformatics",
            parameters="",
            license=", ".join(t for t in m.get("tags", []) if "license" in t.lower()),
            description=f"Auto-discovered from HuggingFace. Pipeline: {m.get('pipeline_tag', 'N/A')}",
        )

        if result.get("success"):
            new_count += 1
            registered.append(model_id)
            logger.info("Registered: %s", model_id)
        else:
            logger.warning("Failed to register %s: %s", model_id, result.get("error"))

    report = {
        "total_scanned": len(models),
        "new_registered": new_count,
        "skipped_existing": skip_count,
        "registered_models": registered,
        "dry_run": dry_run,
    }

    logger.info(
        "Scan complete: %d scanned, %d new, %d skipped",
        len(models), new_count, skip_count,
    )

    return report


def run_consistency_check() -> int:
    """Run memory consistency check and return exit code."""
    script = PROJECT_ROOT / "scripts" / "memory_consistency_check.py"
    if not script.exists():
        logger.warning("memory_consistency_check.py not found, skipping")
        return 0

    logger.info("Running memory consistency check...")
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        logger.info("Consistency check passed")
    else:
        logger.warning("Consistency check returned code %d", result.returncode)
        if result.stdout:
            logger.info(result.stdout)
        if result.stderr:
            logger.warning(result.stderr)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Scout Agent automated scan")
    parser.add_argument(
        "--tags", nargs="+",
        default=["biology", "single-cell", "protein", "genomics", "scRNA", "ESM"],
        help="HuggingFace search tags",
    )
    parser.add_argument(
        "--authors", nargs="+",
        default=["facebook", "bowang-lab", "ctheodoris", "InstaDeepAI"],
        help="HuggingFace authors to monitor",
    )
    parser.add_argument("--days", type=int, default=7, help="Look back N days")
    parser.add_argument("--limit", type=int, default=50, help="Max models to return")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--skip-consistency", action="store_true", help="Skip consistency check")
    args = parser.parse_args()

    report = asyncio.run(run_scan(
        tags=args.tags,
        authors=args.authors,
        days_back=args.days,
        limit=args.limit,
        dry_run=args.dry_run,
    ))

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if not args.skip_consistency and not args.dry_run:
        run_consistency_check()


if __name__ == "__main__":
    main()
