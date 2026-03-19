"""
memory_rotate.py — BioOpenClaw 记忆轮换脚本

功能：扫描所有 Agent 的 MEMORY.md，将超过 200 行的最旧条目归档到对应 topic 文件。
运行频率：每周（建议周一早上）
用法：python scripts/memory_rotate.py [--agent <agent_name>] [--dry-run]
"""

import argparse
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = PROJECT_ROOT / "agents"
MAX_LINES = 200

AGENTS = ["scout_agent", "data_agent", "model_agent", "research_agent", "watcher"]

TOPIC_ROUTING_DEFAULTS: dict[str, dict[str, str]] = {
    "scout_agent": {
        "HuggingFace": "huggingface_monitoring.md",
        "benchmark": "benchmark_tracking.md",
        "基准": "benchmark_tracking.md",
    },
    "data_agent": {
        "GEO": "geo_download.md",
        "Scanpy": "scanpy_qc.md",
        "质控": "scanpy_qc.md",
        "批次": "batch_correction.md",
        "Harmony": "batch_correction.md",
        "scVI": "batch_correction.md",
    },
    "model_agent": {
        "LoRA": "lora_finetuning.md",
        "QLoRA": "lora_finetuning.md",
        "微调": "lora_finetuning.md",
        "Triton": "triton_serving.md",
        "vLLM": "triton_serving.md",
        "推理": "triton_serving.md",
    },
    "research_agent": {
        "假设": "hypothesis_generation.md",
        "统计": "statistical_testing.md",
        "p值": "statistical_testing.md",
        "FDR": "statistical_testing.md",
    },
    "watcher": {
        "循环": "loop_detection.md",
        "哈希": "loop_detection.md",
        "steering": "steering_patterns.md",
        "纠偏": "steering_patterns.md",
    },
}


def parse_memory_sections(content: str) -> dict[str, list[str]]:
    """解析 MEMORY.md 的三个固定 section。"""
    sections: dict[str, list[str]] = {
        "Topic Routing": [],
        "Core Lessons": [],
        "Active Warnings": [],
        "header": [],
    }
    current_section = "header"
    for line in content.splitlines():
        if line.strip() == "## Topic Routing":
            current_section = "Topic Routing"
        elif line.strip() == "## Core Lessons":
            current_section = "Core Lessons"
        elif line.strip() == "## Active Warnings":
            current_section = "Active Warnings"
        else:
            sections[current_section].append(line)
    return sections


def classify_lesson(lesson: str, agent_name: str) -> str:
    """根据教训内容和关键词路由表，确定归档到哪个 topic 文件。"""
    routing = TOPIC_ROUTING_DEFAULTS.get(agent_name, {})
    for keyword, topic_file in routing.items():
        if keyword.lower() in lesson.lower():
            return topic_file
    return "misc_lessons.md"


def archive_to_topic(
    topic_path: Path, lessons: list[str], agent_name: str, dry_run: bool
) -> None:
    """将教训列表归档到对应的 topic 文件。"""
    if not lessons:
        return
    archive_block = "\n".join(f"- {l}" if not l.startswith("- ") else l for l in lessons)
    archive_section = f"\n\n## Archived Lessons — {datetime.now().strftime('%Y-%m-%d')}\n\n{archive_block}\n"

    if dry_run:
        logger.info(f"[DRY-RUN] Would append {len(lessons)} lessons to {topic_path}")
        return

    topic_path.parent.mkdir(parents=True, exist_ok=True)
    if not topic_path.exists():
        topic_path.write_text(
            f"# {topic_path.stem.replace('_', ' ').title()} — Archived Lessons\n\n"
            f"> 由 memory_rotate.py 自动生成，包含从 MEMORY.md 归档的旧教训\n"
        )
    with topic_path.open("a", encoding="utf-8") as f:
        f.write(archive_section)
    logger.info(f"  归档 {len(lessons)} 条教训到 {topic_path.name}")


def rotate_agent_memory(agent_name: str, dry_run: bool) -> bool:
    """轮换单个 Agent 的 MEMORY.md。返回是否执行了轮换。"""
    memory_path = AGENTS_DIR / agent_name / "MEMORY.md"
    if not memory_path.exists():
        logger.warning(f"MEMORY.md 不存在: {memory_path}")
        return False

    content = memory_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    if len(lines) <= MAX_LINES:
        logger.info(f"[{agent_name}] {len(lines)} 行，无需轮换")
        return False

    logger.info(f"[{agent_name}] {len(lines)} 行，超过 {MAX_LINES} 行上限，开始轮换...")

    sections = parse_memory_sections(content)
    lessons = [l for l in sections["Core Lessons"] if l.strip().startswith("- [")]

    excess_count = len(lines) - MAX_LINES
    # 最旧的教训在列表末尾（因为 Core Lessons 按降序排列）
    lessons_to_archive = lessons[-excess_count:] if excess_count < len(lessons) else lessons[1:]

    # 按 topic 分组归档
    topic_buckets: dict[str, list[str]] = {}
    for lesson in lessons_to_archive:
        topic_file = classify_lesson(lesson, agent_name)
        topic_buckets.setdefault(topic_file, []).append(lesson)

    topics_dir = AGENTS_DIR / agent_name / "topics"
    for topic_file, bucket in topic_buckets.items():
        archive_to_topic(topics_dir / topic_file, bucket, agent_name, dry_run)

    # 更新 MEMORY.md，移除已归档的教训
    archived_set = set(lessons_to_archive)
    new_lessons = [l for l in sections["Core Lessons"] if l not in archived_set]

    new_content_parts = [
        "\n".join(sections["header"]),
        "\n## Topic Routing\n",
        "\n".join(sections["Topic Routing"]),
        "\n## Core Lessons\n",
        "\n".join(new_lessons),
        "\n## Active Warnings\n",
        "\n".join(sections["Active Warnings"]),
    ]
    new_content = "\n".join(new_content_parts)

    if dry_run:
        logger.info(f"[DRY-RUN] Would update {memory_path} (remove {len(lessons_to_archive)} lessons)")
    else:
        # 备份原文件
        backup_path = memory_path.with_suffix(f".bak.{datetime.now().strftime('%Y%m%d')}")
        shutil.copy2(memory_path, backup_path)
        memory_path.write_text(new_content, encoding="utf-8")
        logger.info(f"  已更新 MEMORY.md，归档了 {len(lessons_to_archive)} 条旧教训")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="BioOpenClaw 记忆轮换脚本")
    parser.add_argument("--agent", choices=AGENTS, help="仅轮换指定 Agent（默认全部）")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入文件")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=== DRY-RUN 模式，不会修改任何文件 ===")

    target_agents = [args.agent] if args.agent else AGENTS
    rotated_count = 0

    for agent_name in target_agents:
        rotated = rotate_agent_memory(agent_name, args.dry_run)
        if rotated:
            rotated_count += 1

    logger.info(f"\n完成：轮换了 {rotated_count}/{len(target_agents)} 个 Agent 的 MEMORY.md")


if __name__ == "__main__":
    main()
