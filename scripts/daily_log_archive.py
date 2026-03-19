"""
daily_log_archive.py — BioOpenClaw 日志归档脚本

功能：将 14 天前的 daily_log 文件移至 daily_log/archive/。
      同样处理 watcher/corrections_log 目录。

运行频率：每日
用法：python scripts/daily_log_archive.py [--days 14] [--dry-run]
"""

import argparse
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = PROJECT_ROOT / "agents"

AGENTS = ["scout_agent", "data_agent", "model_agent", "research_agent", "watcher"]
DATE_FORMAT = "%Y-%m-%d"


def archive_log_directory(log_dir: Path, archive_days: int, dry_run: bool) -> int:
    """
    归档指定目录中超过 archive_days 天的 .md 文件到 archive/ 子目录。
    返回归档的文件数量。
    """
    if not log_dir.exists():
        return 0

    cutoff_date = datetime.now() - timedelta(days=archive_days)
    archive_dir = log_dir / "archive"
    archived_count = 0

    for log_file in sorted(log_dir.glob("*.md")):
        # 尝试从文件名解析日期（格式：YYYY-MM-DD.md）
        try:
            file_date = datetime.strptime(log_file.stem, DATE_FORMAT)
        except ValueError:
            logger.debug(f"跳过非日期命名文件: {log_file.name}")
            continue

        if file_date < cutoff_date:
            dest_path = archive_dir / log_file.name
            if dry_run:
                logger.info(f"  [DRY-RUN] Would archive: {log_file.relative_to(PROJECT_ROOT)}")
            else:
                archive_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(log_file), str(dest_path))
                logger.info(f"  已归档: {log_file.name} → archive/")
            archived_count += 1

    return archived_count


def main() -> None:
    parser = argparse.ArgumentParser(description="BioOpenClaw 日志归档脚本")
    parser.add_argument("--days", type=int, default=14, help="保留最近 N 天的日志（默认 14）")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不移动文件")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=== DRY-RUN 模式，不会移动任何文件 ===")

    cutoff = datetime.now() - timedelta(days=args.days)
    logger.info(f"归档策略：移动 {cutoff.strftime(DATE_FORMAT)} 之前的日志文件")

    total_archived = 0

    for agent in AGENTS:
        agent_dir = AGENTS_DIR / agent

        # 归档 daily_log
        daily_log_dir = agent_dir / "daily_log"
        count = archive_log_directory(daily_log_dir, args.days, args.dry_run)
        if count > 0:
            logger.info(f"[{agent}] daily_log: 归档了 {count} 个文件")
        else:
            logger.info(f"[{agent}] daily_log: 无需归档")
        total_archived += count

        # Watcher 额外归档 corrections_log
        if agent == "watcher":
            corrections_dir = agent_dir / "corrections_log"
            count = archive_log_directory(corrections_dir, args.days, args.dry_run)
            if count > 0:
                logger.info(f"[watcher] corrections_log: 归档了 {count} 个文件")
            total_archived += count

    logger.info(f"\n完成：共归档 {total_archived} 个日志文件")


if __name__ == "__main__":
    main()
