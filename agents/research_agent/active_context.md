---
last_session: 2026-03-15T00:00:00
---

# Active Context — Research Agent

## Current Focus
- 初始化完成，等待文献检索任务
- MCP 工具 `search_literature` 已实现，待测试

## Blocked
<!-- 无阻塞项 -->

## Next Steps
1. 验证 MCP 连接：`scripts/test_mcp_connection.py`
2. 确认 `search_literature` 通过 MCP 可调用
3. 初始化文献知识库：建立 `shared_memory/literature/` 的第一个主题文件

## Recent Decisions
- [2026-03-15] 使用 Entrez API（BioPython）作为 PubMed 检索工具，设置 ENTREZ_EMAIL 环境变量
- [2026-03-15] 文献知识库初始主题：单细胞基础模型综述

## Incoming Messages
<!-- 来自其他 Agent 的 inbox 消息将追加在此处 -->
