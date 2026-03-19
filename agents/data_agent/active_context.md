---
last_session: 2026-03-19T00:00:00
---

# Active Context — Data Agent

## Current Focus
- Phase 1 MVP 完成：17 个 MCP 工具已实现并通过测试
- 数据源覆盖：GEO、TCGA、CellxGene Census、UniProt、PDB
- 数据处理：QC、归一化、批次校正、格式转换、多组学整合
- 基础设施：谱系追踪、数据版本管理、管道编排、QC 报告
- 等待用户发送研究方案或数据处理指令

## Blocked
<!-- 无阻塞项 -->

## Next Steps
1. 接收用户研究方案，执行 8 步工作流程
2. 根据实际使用积累 Core Lessons 到 MEMORY.md
3. 等待 Phase 2 集成：lakeFS 版本控制、LaminDB 本体验证

## Recent Decisions
- [2026-03-19] 新增 UniProt + PDB 数据源工具，覆盖蛋白质序列/结构检索
- [2026-03-19] 引入 Muon 多组学处理，支持 CITE-seq/Multiome/Spatial
- [2026-03-19] 实现本地版本管理（snapshot/list/restore），作为 Phase 1 lakeFS 替代
- [2026-03-19] 添加拒绝超范围任务的行为边界
- [2026-03-15] 使用 GEOparse 作为 GEO 数据下载的主要工具（比直接 FTP 更稳定）
- [2026-03-15] 默认 QC 参数：min_genes=200, min_cells=3, mt_pct<20%

## Incoming Messages
<!-- 来自其他 Agent 的 inbox 消息将追加在此处 -->
