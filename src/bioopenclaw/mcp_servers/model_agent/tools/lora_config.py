"""LoRA/QLoRA configuration generator."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.model_agent.config import get_config

logger = logging.getLogger(__name__)

RECOMMENDED_PARAMS: dict[str, dict[str, Any]] = {
    "scGPT": {"rank": 8, "alpha": 16, "lr": 2e-4, "target_modules": ["query", "value"]},
    "ESM2": {"rank": 16, "alpha": 32, "lr": 1e-4, "target_modules": ["query", "key", "value"]},
    "ESM2-650M": {"rank": 16, "alpha": 32, "lr": 1e-4, "target_modules": ["query", "key", "value"]},
    "Geneformer": {"rank": 8, "alpha": 16, "lr": 2e-4, "target_modules": ["query", "value"]},
}


async def create_lora_config(
    base_model: str,
    task_type: str = "classification",
    method: str = "lora",
    rank: int | None = None,
    alpha: int | None = None,
    learning_rate: float | None = None,
    epochs: int | None = None,
    batch_size: int | None = None,
    target_modules: list[str] | None = None,
    quantization_bits: int | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate a LoRA/QLoRA fine-tuning configuration.

    Uses recommended defaults from SOUL.md when parameters are not specified.
    """
    cfg = get_config()

    recommended = {}
    for key, params in RECOMMENDED_PARAMS.items():
        if key.lower() in base_model.lower():
            recommended = params
            break

    lora_rank = rank or recommended.get("rank", cfg.default_lora_rank)
    lora_alpha = alpha or recommended.get("alpha", cfg.default_lora_alpha)
    lr = learning_rate or recommended.get("lr", cfg.default_learning_rate)
    modules = target_modules or recommended.get("target_modules", ["query", "value"])

    config = {
        "base_model": base_model,
        "method": method,
        "task_type": task_type,
        "peft_config": {
            "peft_type": "LORA",
            "r": lora_rank,
            "lora_alpha": lora_alpha,
            "lora_dropout": 0.1,
            "target_modules": modules,
            "bias": "none",
            "task_type": task_type.upper().replace("-", "_"),
        },
        "training_args": {
            "learning_rate": lr,
            "num_train_epochs": epochs or cfg.default_epochs,
            "per_device_train_batch_size": batch_size or cfg.default_batch_size,
            "gradient_accumulation_steps": 4,
            "warmup_ratio": 0.1,
            "weight_decay": 0.01,
            "logging_steps": 10,
            "save_strategy": "epoch",
            "evaluation_strategy": "epoch",
            "fp16": True,
        },
        "used_recommended_params": bool(recommended),
        "recommended_source": next(
            (k for k in RECOMMENDED_PARAMS if k.lower() in base_model.lower()), None
        ),
    }

    if method.lower() == "qlora" or quantization_bits:
        bits = quantization_bits or 4
        config["quantization"] = {
            "load_in_4bit": bits == 4,
            "load_in_8bit": bits == 8,
            "bnb_4bit_compute_dtype": "float16",
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_use_double_quant": True,
        }

    if output_path:
        try:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
            config["saved_to"] = str(out)
            logger.info("LoRA config saved to %s", out)
        except Exception as e:
            logger.error("Failed to save config: %s", e)
            return {"success": False, "error": str(e)}

    return {"success": True, "config": config}
