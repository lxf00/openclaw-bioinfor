# Watcher Memory

> **写入者**: Watcher（仅本 Agent 可修改）
> **上限**: 200 行（超出由 memory_rotate.py 归档到 topics/）
> **Schema**: 仅允许以下三个 section，禁止新增

---

## Topic Routing

| 关键词 | 对应 Topic 文件 |
|--------|---------------|
| 循环检测, 哈希对比, 重复行为, 无限循环 | `topics/loop_detection.md` |
| steering, 纠偏策略, 停滞检测, 行为干预 | `topics/steering_patterns.md` |

---

## Core Lessons

<!-- 按日期降序排列，最新在前。格式：[YYYY-MM-DD] <教训内容> -->
- [2026-03-15] 初始化：Watcher 记忆系统建立，循环检测和纠偏框架已搭建
- [2026-03-15] 层级 1 触发（3次重复工具调用）应立即发送高优先级 steering 消息，不应等待
- [2026-03-15] steering 消息的语气应是协作式的（"建议..."）而非命令式的（"必须..."），后者会触发防御反应

---

## Active Warnings

<!-- 当前需要注意的短期警告，过期后移除 -->
- corrections_log 文件需要每日备份，因为它是 Watcher 自我优化的唯一数据来源
- 避免过度纠偏：如果一个 Agent 在合理地重试（如网络故障），哈希对比应排除 retry 标志参数
