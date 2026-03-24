"""Training monitor — reads training logs and checkpoint status."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.model_agent.config import get_config

logger = logging.getLogger(__name__)


async def check_training_status(
    project_name: str | None = None,
    checkpoint_dir: str | None = None,
) -> dict[str, Any]:
    """Check the status of training jobs by inspecting checkpoint directories.

    Reads ``trainer_state.json`` from HuggingFace Trainer checkpoints
    and/or scans for checkpoint directories.
    """
    cfg = get_config()
    base_dir = Path(checkpoint_dir or cfg.checkpoints_dir)

    if not base_dir.exists():
        return {
            "success": True,
            "status": "no_checkpoints",
            "message": f"Checkpoint directory does not exist: {base_dir}",
            "jobs": [],
        }

    jobs: list[dict[str, Any]] = []

    search_dirs = [base_dir]
    if project_name:
        project_dir = base_dir / project_name
        if project_dir.exists():
            search_dirs = [project_dir]
        else:
            return {
                "success": True,
                "status": "not_found",
                "message": f"Project '{project_name}' not found in {base_dir}",
                "jobs": [],
            }

    for search_dir in search_dirs:
        checkpoint_dirs = sorted(
            [d for d in search_dir.iterdir() if d.is_dir() and d.name.startswith("checkpoint-")],
            key=lambda d: d.name,
        )

        if not checkpoint_dirs:
            for sub in search_dir.iterdir():
                if sub.is_dir():
                    sub_checkpoints = sorted(
                        [d for d in sub.iterdir() if d.is_dir() and d.name.startswith("checkpoint-")],
                        key=lambda d: d.name,
                    )
                    if sub_checkpoints:
                        jobs.append(_parse_training_job(sub, sub_checkpoints))
        else:
            jobs.append(_parse_training_job(search_dir, checkpoint_dirs))

    return {
        "success": True,
        "status": "found" if jobs else "no_training_jobs",
        "total_jobs": len(jobs),
        "jobs": jobs,
    }


def _parse_training_job(job_dir: Path, checkpoint_dirs: list[Path]) -> dict[str, Any]:
    """Parse training job info from checkpoint directory structure."""
    latest_checkpoint = checkpoint_dirs[-1]
    trainer_state_file = latest_checkpoint / "trainer_state.json"

    job_info: dict[str, Any] = {
        "name": job_dir.name,
        "path": str(job_dir),
        "total_checkpoints": len(checkpoint_dirs),
        "latest_checkpoint": latest_checkpoint.name,
    }

    if trainer_state_file.exists():
        try:
            state = json.loads(trainer_state_file.read_text(encoding="utf-8"))
            job_info.update({
                "current_epoch": state.get("epoch"),
                "global_step": state.get("global_step"),
                "best_metric": state.get("best_metric"),
                "best_model_checkpoint": state.get("best_model_checkpoint"),
                "total_flos": state.get("total_flos"),
            })

            log_history = state.get("log_history", [])
            if log_history:
                latest_log = log_history[-1]
                job_info["latest_log"] = {
                    k: v for k, v in latest_log.items()
                    if k in ("loss", "eval_loss", "learning_rate", "epoch", "step")
                }

                eval_logs = [l for l in log_history if "eval_loss" in l]
                if eval_logs:
                    job_info["eval_history"] = [
                        {"epoch": l.get("epoch"), "eval_loss": l.get("eval_loss")}
                        for l in eval_logs[-5:]
                    ]
        except (json.JSONDecodeError, KeyError) as e:
            job_info["parse_error"] = str(e)

    return job_info
