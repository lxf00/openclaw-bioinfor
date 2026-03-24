"""Hypothesis generation — produces structured scientific hypotheses."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def generate_hypothesis(
    background: str,
    observation: str,
    h0: str = "",
    h1: str = "",
    suggested_test: str = "",
    data_requirements: str = "",
    literature_refs: list[str] | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate a structured scientific hypothesis document.

    If *h0* and *h1* are not provided, generates a template with placeholders.
    If *output_path* is specified, writes the hypothesis as a Markdown file.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    refs = literature_refs or []

    h0_text = h0 or "[待填写：零假设]"
    h1_text = h1 or "[待填写：备择假设]"
    test_text = suggested_test or "[待填写：统计检验方法]"
    data_text = data_requirements or "[待填写：数据要求]"

    hypothesis_doc = {
        "background": background,
        "observation": observation,
        "hypotheses": {
            "H0": h0_text,
            "H1": h1_text,
        },
        "test_plan": {
            "method": test_text,
            "data_requirements": data_text,
            "significance_level": 0.05,
            "multiple_testing_correction": "BH-FDR",
        },
        "literature_support": refs,
        "generated_date": today,
        "status": "draft",
    }

    md_content = (
        f"---\n"
        f"type: hypothesis\n"
        f"date: {today}\n"
        f"status: draft\n"
        f"generated_by: research_agent\n"
        f"---\n"
        f"\n"
        f"# Scientific Hypothesis\n"
        f"\n"
        f"## Background\n"
        f"\n"
        f"{background}\n"
        f"\n"
        f"## Observation\n"
        f"\n"
        f"{observation}\n"
        f"\n"
        f"## Hypotheses\n"
        f"\n"
        f"- **H0 (Null)**: {h0_text}\n"
        f"- **H1 (Alternative)**: {h1_text}\n"
        f"\n"
        f"## Test Plan\n"
        f"\n"
        f"- **Method**: {test_text}\n"
        f"- **Data requirements**: {data_text}\n"
        f"- **Significance level**: 0.05\n"
        f"- **Multiple testing correction**: BH-FDR\n"
        f"\n"
        f"## Literature Support\n"
        f"\n"
    )

    if refs:
        for i, ref in enumerate(refs, 1):
            md_content += f"{i}. {ref}\n"
    else:
        md_content += "*No references provided yet.*\n"

    md_content += (
        f"\n"
        f"## Expected Results\n"
        f"\n"
        f"*Describe what results would support or reject the hypothesis.*\n"
        f"\n"
        f"## Limitations\n"
        f"\n"
        f"*Describe known limitations of this hypothesis and test plan.*\n"
    )

    if output_path:
        try:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(md_content, encoding="utf-8")
            hypothesis_doc["output_path"] = str(out)
            logger.info("Hypothesis written to %s", out)
        except Exception as e:
            logger.error("Failed to write hypothesis: %s", e)
            return {"success": False, "error": str(e)}

    return {
        "success": True,
        "hypothesis": hypothesis_doc,
        "markdown_preview": md_content[:500] + "...",
    }
