"""
memory_consistency_check.py — BioOpenClaw 记忆一致性校验脚本

功能：
1. 比对各 _index.md 与实际文件是否一致（检测孤儿文件和幽灵索引）
2. 检查所有 MEMORY.md 是否超过 200 行上限
3. 检查所有 Core Lessons 是否带日期戳
4. 输出校验报告

运行频率：每日
用法：python scripts/memory_consistency_check.py [--fix]
退出码：0=通过，1=发现问题
"""

import argparse
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = PROJECT_ROOT / "agents"
SHARED_MEMORY_DIR = PROJECT_ROOT / "shared_memory"
MAX_LINES = 200

AGENTS = ["scout_agent", "data_agent", "model_agent", "research_agent", "watcher"]
DATE_STAMP_PATTERN = re.compile(r"^\- \[\d{4}-\d{2}-\d{2}\]")


@dataclass
class CheckReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        logger.error(f"  [ERROR] {msg}")

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning(f"  [WARN]  {msg}")

    def add_info(self, msg: str) -> None:
        self.info.append(msg)
        logger.info(f"  [OK]    {msg}")

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


def check_memory_line_count(report: CheckReport) -> None:
    """检查所有 MEMORY.md 是否超过 200 行。"""
    logger.info("\n=== 检查 MEMORY.md 行数上限 ===")
    for agent in AGENTS:
        memory_path = AGENTS_DIR / agent / "MEMORY.md"
        if not memory_path.exists():
            report.add_error(f"{agent}/MEMORY.md 不存在")
            continue
        line_count = len(memory_path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_LINES:
            report.add_error(
                f"{agent}/MEMORY.md 超过上限：{line_count} 行（上限 {MAX_LINES}）"
                f"——请运行 memory_rotate.py"
            )
        elif line_count > MAX_LINES * 0.9:
            report.add_warning(
                f"{agent}/MEMORY.md 接近上限：{line_count} 行（上限 {MAX_LINES}）"
            )
        else:
            report.add_info(f"{agent}/MEMORY.md: {line_count} 行")


def check_date_stamps(report: CheckReport) -> None:
    """检查所有 MEMORY.md 的 Core Lessons 是否带日期戳。"""
    logger.info("\n=== 检查 Core Lessons 日期戳 ===")
    for agent in AGENTS:
        memory_path = AGENTS_DIR / agent / "MEMORY.md"
        if not memory_path.exists():
            continue
        content = memory_path.read_text(encoding="utf-8")
        in_core_lessons = False
        bad_lines = []
        for i, line in enumerate(content.splitlines(), 1):
            if "## Core Lessons" in line:
                in_core_lessons = True
                continue
            if line.startswith("## ") and in_core_lessons:
                in_core_lessons = False
            if in_core_lessons and line.strip().startswith("- ") and not line.strip().startswith("- [20"):
                if "<!-- " not in line:  # 跳过注释行
                    bad_lines.append(f"L{i}: {line.strip()[:60]}")
        if bad_lines:
            for bad in bad_lines:
                report.add_error(f"{agent}/MEMORY.md Core Lessons 缺少日期戳: {bad}")
        else:
            report.add_info(f"{agent}/MEMORY.md Core Lessons 日期戳检查通过")


def check_model_registry_index(report: CheckReport) -> None:
    """检查 model_registry/_index.md 与实际文件的一致性。"""
    logger.info("\n=== 检查 model_registry 索引一致性 ===")
    registry_dir = SHARED_MEMORY_DIR / "model_registry"
    index_path = registry_dir / "_index.md"

    if not index_path.exists():
        report.add_error("shared_memory/model_registry/_index.md 不存在")
        return

    # 读取索引中列出的模型
    index_content = index_path.read_text(encoding="utf-8")
    indexed_files = set(re.findall(r"\[(\w+\.md)\]", index_content))

    # 实际存在的模型文件
    actual_files = {f.name for f in registry_dir.glob("*.md") if f.name != "_index.md"}

    # 幽灵索引（索引有但文件不存在）
    ghost_entries = indexed_files - actual_files
    for ghost in ghost_entries:
        report.add_error(f"model_registry/_index.md 引用了不存在的文件: {ghost}")

    # 孤儿文件（文件存在但不在索引中）
    orphan_files = actual_files - indexed_files
    for orphan in orphan_files:
        report.add_warning(f"model_registry/ 存在孤儿文件（不在索引中）: {orphan}")

    if not ghost_entries and not orphan_files:
        report.add_info(f"model_registry 索引一致性通过（{len(actual_files)} 个模型文件）")


def check_experiments_index(report: CheckReport) -> None:
    """检查 experiments/_index.md 与实际文件的一致性。"""
    logger.info("\n=== 检查 experiments 索引一致性 ===")
    experiments_dir = SHARED_MEMORY_DIR / "experiments"
    index_path = experiments_dir / "_index.md"

    if not index_path.exists():
        report.add_error("shared_memory/experiments/_index.md 不存在")
        return

    actual_files = {f.name for f in experiments_dir.glob("*.md") if f.name != "_index.md"}
    if not actual_files:
        report.add_info("experiments/ 目录为空（尚无实验记录）")
        return

    index_content = index_path.read_text(encoding="utf-8")
    orphans = [f for f in actual_files if f not in index_content]
    for orphan in orphans:
        report.add_warning(f"experiments/ 存在孤儿文件（不在索引中）: {orphan}")

    if not orphans:
        report.add_info(f"experiments 索引一致性通过（{len(actual_files)} 个实验记录）")


def check_agent_directory_structure(report: CheckReport) -> None:
    """检查每个 Agent 目录结构完整性。"""
    logger.info("\n=== 检查 Agent 目录结构 ===")
    required_files = ["SOUL.md", "MEMORY.md", "active_context.md"]
    required_dirs = ["topics", "daily_log"]

    for agent in AGENTS:
        agent_dir = AGENTS_DIR / agent
        if not agent_dir.exists():
            report.add_error(f"agents/{agent}/ 目录不存在")
            continue
        for req_file in required_files:
            if not (agent_dir / req_file).exists():
                report.add_error(f"agents/{agent}/{req_file} 不存在")
        for req_dir in required_dirs:
            if not (agent_dir / req_dir).exists():
                report.add_warning(f"agents/{agent}/{req_dir}/ 目录不存在（将在首次使用时创建）")

        # Watcher 需要额外的 corrections_log 目录
        if agent == "watcher" and not (agent_dir / "corrections_log").exists():
            report.add_warning("agents/watcher/corrections_log/ 目录不存在")


def check_shared_memory_structure(report: CheckReport) -> None:
    """检查 shared_memory 目录结构完整性。"""
    logger.info("\n=== 检查 shared_memory 结构 ===")
    required_files = ["_index.md", "conventions.md", "known_issues.md"]
    required_subdirs = ["model_registry", "literature", "experiments", "inbox"]

    for req_file in required_files:
        if not (SHARED_MEMORY_DIR / req_file).exists():
            report.add_error(f"shared_memory/{req_file} 不存在")
        else:
            report.add_info(f"shared_memory/{req_file} 存在")

    for req_dir in required_subdirs:
        if not (SHARED_MEMORY_DIR / req_dir).exists():
            report.add_error(f"shared_memory/{req_dir}/ 目录不存在")
        else:
            report.add_info(f"shared_memory/{req_dir}/ 存在")


def print_summary(report: CheckReport) -> None:
    """打印校验摘要。"""
    print("\n" + "=" * 60)
    print("BioOpenClaw 记忆一致性校验报告")
    print("=" * 60)
    print(f"  错误:   {len(report.errors)}")
    print(f"  警告:   {len(report.warnings)}")
    print(f"  通过:   {len(report.info)}")

    if report.errors:
        print("\n[错误列表]")
        for err in report.errors:
            print(f"  ✗ {err}")

    if report.warnings:
        print("\n[警告列表]")
        for warn in report.warnings:
            print(f"  ⚠ {warn}")

    if report.has_errors:
        print("\n结论：校验失败，请修复以上错误。")
    else:
        print("\n结论：校验通过！记忆系统状态健康。")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="BioOpenClaw 记忆一致性校验")
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题（实验性）")
    args = parser.parse_args()

    report = CheckReport()

    check_agent_directory_structure(report)
    check_shared_memory_structure(report)
    check_memory_line_count(report)
    check_date_stamps(report)
    check_model_registry_index(report)
    check_experiments_index(report)

    print_summary(report)
    sys.exit(1 if report.has_errors else 0)


if __name__ == "__main__":
    main()
