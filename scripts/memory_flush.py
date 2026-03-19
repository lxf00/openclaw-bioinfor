"""
memory_flush.py — BioOpenClaw 会话结束记忆同步脚本

功能：
1. 更新目标 Agent 的 active_context.md（会话状态）
2. 追加今日 daily_log 条目
3. 如有新教训，追加到 MEMORY.md 的 Core Lessons

用法：
  python scripts/memory_flush.py --agent data_agent --focus "完成 BRCA1 数据质控" \
      --lesson "[2026-03-15] Scanpy QC 时线粒体基因过滤阈值 20% 适合大多数场景"

  # 交互模式（无参数时）
  python scripts/memory_flush.py --agent data_agent
"""

import argparse
import logging
import re
import sys
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
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

AGENTS = ["scout_agent", "data_agent", "model_agent", "research_agent", "watcher"]


def update_active_context(
    agent_name: str,
    current_focus: str | None,
    blocked: str | None,
    next_steps: str | None,
    decision: str | None,
) -> bool:
    """更新 active_context.md 的指定字段。返回是否成功更新。"""
    context_path = AGENTS_DIR / agent_name / "active_context.md"
    if not context_path.exists():
        logger.error(f"active_context.md 不存在: {context_path}")
        return False

    content = context_path.read_text(encoding="utf-8")
    now = datetime.now().strftime(DATETIME_FORMAT)

    # 更新 last_session 时间戳
    content = re.sub(
        r"last_session:.*",
        f"last_session: {now}",
        content,
    )

    # 追加 Current Focus（如果提供）
    if current_focus:
        # 找到 ## Current Focus 区段，在其下插入
        focus_marker = "## Current Focus"
        if focus_marker in content:
            idx = content.index(focus_marker) + len(focus_marker)
            content = content[:idx] + f"\n- {current_focus}" + content[idx:]
        logger.info(f"  已更新 Current Focus: {current_focus[:50]}...")

    # 追加 Recent Decisions（如果提供）
    if decision:
        decision_marker = "## Recent Decisions"
        dated_decision = f"[{datetime.now().strftime(DATE_FORMAT)}] {decision}"
        if decision_marker in content:
            idx = content.index(decision_marker) + len(decision_marker)
            content = content[:idx] + f"\n- {dated_decision}" + content[idx:]
        logger.info(f"  已追加 Decision: {decision[:50]}...")

    # 更新 Blocked（如果提供）
    if blocked is not None:
        blocked_marker = "## Blocked"
        if blocked_marker in content:
            # 清除现有 Blocked 内容，写入新内容
            next_section = re.search(r"\n## ", content[content.index(blocked_marker) + len(blocked_marker):])
            if next_section:
                section_end = content.index(blocked_marker) + len(blocked_marker) + next_section.start()
                new_blocked = f"\n{blocked}\n" if blocked else "\n<!-- 无阻塞项 -->\n"
                content = (
                    content[: content.index(blocked_marker) + len(blocked_marker)]
                    + new_blocked
                    + content[section_end:]
                )
        logger.info(f"  已更新 Blocked: {blocked[:50] if blocked else '（清空）'}...")

    context_path.write_text(content, encoding="utf-8")
    return True


def append_daily_log(
    agent_name: str,
    log_entry: str,
    done: str = "",
    blocked: str = "",
    decisions: str = "",
    lessons: str = "",
) -> None:
    """追加条目到今日 daily_log 文件。"""
    today = datetime.now().strftime(DATE_FORMAT)
    log_dir = AGENTS_DIR / agent_name / "daily_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{today}.md"

    now_time = datetime.now().strftime("%H:%M")
    header = f"\n{now_time} - {log_entry}"

    entry_parts = [header]
    if done:
        entry_parts.append(f"**Done:** {done}")
    if blocked:
        entry_parts.append(f"**Blocked:** {blocked}")
    if decisions:
        entry_parts.append(f"**Decisions:** {decisions}")
    if lessons:
        entry_parts.append(f"**Lessons:** {lessons}")
    entry_parts.append("")

    entry_text = "\n".join(entry_parts)

    if not log_path.exists():
        log_path.write_text(
            f"# {agent_name.replace('_', ' ').title()} Daily Log — {today}\n",
            encoding="utf-8",
        )

    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry_text)
    logger.info(f"  已追加 daily_log 条目: {log_path.name}")


def append_lesson_to_memory(agent_name: str, lesson: str) -> bool:
    """将新教训追加到 MEMORY.md 的 Core Lessons 区段（最新在前）。"""
    memory_path = AGENTS_DIR / agent_name / "MEMORY.md"
    if not memory_path.exists():
        logger.error(f"MEMORY.md 不存在: {memory_path}")
        return False

    content = memory_path.read_text(encoding="utf-8")

    # 确保教训带日期戳
    if not re.match(r"^\[20\d{2}-\d{2}-\d{2}\]", lesson):
        today = datetime.now().strftime(DATE_FORMAT)
        lesson = f"[{today}] {lesson}"

    # 在 Core Lessons 后插入新教训（降序排列，最新在前）
    lessons_marker = "## Core Lessons"
    if lessons_marker not in content:
        logger.error(f"MEMORY.md 中未找到 '## Core Lessons' section")
        return False

    idx = content.index(lessons_marker) + len(lessons_marker)
    # 跳过注释行
    insert_point = content.find("\n- [", idx)
    if insert_point == -1:
        insert_point = content.find("\n", idx)

    content = content[:insert_point] + f"\n- {lesson}" + content[insert_point:]
    memory_path.write_text(content, encoding="utf-8")

    # 检查是否超过 200 行
    line_count = len(content.splitlines())
    if line_count > MAX_LINES:
        logger.warning(
            f"  MEMORY.md 现在有 {line_count} 行，超过 {MAX_LINES} 行上限！"
            f"  请运行 scripts/memory_rotate.py 进行归档。"
        )

    logger.info(f"  已追加教训到 MEMORY.md: {lesson[:60]}...")
    return True


def interactive_mode(agent_name: str) -> None:
    """交互模式：引导用户输入会话信息。"""
    print(f"\n=== BioOpenClaw Memory Flush — {agent_name} ===")
    print("（直接回车跳过对应字段）\n")

    current_focus = input("本次会话完成的工作（Current Focus）: ").strip()
    blocked = input("当前阻塞项（Blocked，回车=无阻塞）: ").strip()
    next_step = input("下一步计划（Next Steps）: ").strip()
    decision = input("本次重要决策（Recent Decision）: ").strip()
    lesson = input("值得记忆的教训（Core Lesson，含日期戳如 [2026-03-15] xxx）: ").strip()
    log_entry = input("日志条目简述（Daily Log）: ").strip()

    if current_focus:
        update_active_context(agent_name, current_focus, blocked if blocked else None, next_step, decision)
    if lesson:
        append_lesson_to_memory(agent_name, lesson)
    if log_entry:
        append_daily_log(agent_name, log_entry, done=current_focus, blocked=blocked, decisions=decision, lessons=lesson)
    print("\n完成！记忆已同步。")


def main() -> None:
    parser = argparse.ArgumentParser(description="BioOpenClaw 会话结束记忆同步脚本")
    parser.add_argument("--agent", choices=AGENTS, required=True, help="目标 Agent 名称")
    parser.add_argument("--focus", help="当前任务焦点（更新 active_context 的 Current Focus）")
    parser.add_argument("--blocked", help="当前阻塞项（更新 active_context 的 Blocked）")
    parser.add_argument("--decision", help="本次重要决策（追加到 Recent Decisions）")
    parser.add_argument("--lesson", help="值得记忆的教训（追加到 MEMORY.md Core Lessons）")
    parser.add_argument("--log", help="日志条目简述（追加到 daily_log）")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    args = parser.parse_args()

    if args.interactive or (not any([args.focus, args.lesson, args.log])):
        interactive_mode(args.agent)
        return

    if args.focus or args.blocked or args.decision:
        update_active_context(args.agent, args.focus, args.blocked, None, args.decision)

    if args.lesson:
        append_lesson_to_memory(args.agent, args.lesson)

    if args.log:
        append_daily_log(
            args.agent,
            args.log,
            done=args.focus or "",
            blocked=args.blocked or "",
            decisions=args.decision or "",
            lessons=args.lesson or "",
        )

    logger.info(f"完成：{args.agent} 记忆已同步")


if __name__ == "__main__":
    main()
