"""Enhanced GEO data download with checksum validation and lineage tracking."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from bioopenclaw.mcp_servers.data_agent.config import get_config
from bioopenclaw.mcp_servers.data_agent.tools.lineage import LineageTimer, record_step
from bioopenclaw.mcp_servers.data_agent.tools.validators import validate_checksum

logger = logging.getLogger(__name__)


async def download_geo_data(
    gse_id: str,
    output_dir: str | None = None,
    email: str | None = None,
    download_supplementary: bool = False,
    project: str | None = None,
) -> dict[str, Any]:
    """Download a GEO dataset with validation and lineage tracking.

    Returns a structured result dict (never raises on data errors).
    """
    try:
        import GEOparse
    except ImportError:
        return {"success": False, "error": "GEOparse not installed: pip install GEOparse"}

    cfg = get_config()
    email = email or cfg.entrez_email or os.environ.get("ENTREZ_EMAIL", "")
    if not email:
        return {
            "success": False,
            "error": (
                "ENTREZ_EMAIL is required. Set DATA_AGENT_ENTREZ_EMAIL env var "
                "or pass email parameter."
            ),
        }

    if output_dir is None:
        output_dir = str(Path(cfg.raw_data_dir) / gse_id)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading GEO dataset: %s → %s", gse_id, out_path)

    with LineageTimer() as timer:
        retries = cfg.download_max_retries
        last_error = ""

        for attempt in range(1, retries + 1):
            try:
                gse = GEOparse.get_GEO(
                    geo=gse_id,
                    destdir=str(out_path),
                    how="brief",
                    email=email,
                )
                break
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Download attempt %d/%d failed: %s", attempt, retries, e,
                )
                if attempt < retries:
                    import asyncio
                    await asyncio.sleep(cfg.download_retry_delay_seconds)
        else:
            return {
                "success": False,
                "error": f"Download failed after {retries} attempts: {last_error}",
                "gse_id": gse_id,
            }

        gsms = list(gse.gsms.keys())
        gpl_info = list(gse.gpls.keys())

        # Post-download: compute checksum on the soft file
        downloaded_files = list(out_path.glob(f"{gse_id}*"))
        checksums = {}
        for f in downloaded_files:
            if f.is_file():
                chk = validate_checksum(str(f))
                if chk["valid"]:
                    checksums[f.name] = chk.get("checksum", "")

        # Detect data format hint from metadata
        data_format_hints = []
        title = gse.metadata.get("title", ["Unknown"])[0]
        summary = gse.metadata.get("summary", [""])[0]
        for keyword in ["log2", "log-transformed", "TPM", "FPKM", "counts", "raw"]:
            if keyword.lower() in summary.lower() or keyword.lower() in title.lower():
                data_format_hints.append(keyword)

    result: dict[str, Any] = {
        "success": True,
        "gse_id": gse_id,
        "title": title,
        "organism": gse.metadata.get("sample_organism_ch1", ["Unknown"])[0],
        "gsm_count": len(gsms),
        "gsm_ids": gsms[:10],
        "platform": gpl_info,
        "output_dir": str(out_path.absolute()),
        "downloaded_files": [f.name for f in downloaded_files],
        "checksums": checksums,
        "data_format_hints": data_format_hints,
        "duration_seconds": round(timer.elapsed, 2),
    }

    if data_format_hints:
        result["warning"] = (
            f"Detected format hints: {data_format_hints}. "
            "Use inspect_dataset to confirm data unit before processing."
        )
    else:
        result["warning"] = (
            "Could not auto-detect data unit from metadata. "
            "Use inspect_dataset to check if data is log-transformed or raw counts."
        )

    if project:
        record_step(
            project=project,
            operation="download_geo_data",
            output_path=str(out_path.absolute()),
            params={"gse_id": gse_id, "download_supplementary": download_supplementary},
            metrics={"gsm_count": len(gsms)},
            checksum=next(iter(checksums.values()), None),
            duration_seconds=timer.elapsed,
        )

    logger.info("Download complete: %s, %d samples", gse_id, len(gsms))
    return result
