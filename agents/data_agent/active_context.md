---
last_session: 2026-03-19T00:00:00
---

# Active Context — Data Agent

## Current Focus
- Phase 1 MVP 完成：17 个 MCP 工具已实现并通过测试
- 数据源覆盖：GEO、TCGA、CellxGene Census、UniProt、PDB
- 数据处理：QC、归一化、批次校正、格式转换、多组学整合
- 基础设施：谱系追踪、数据版本管理、管道编排、QC 报告
- 已引入 Graduated Autonomy 模型：收到研究方案后自主完成全流程，不在中间步骤暂停

## Blocked
<!-- 无阻塞项 -->

## Next Steps
1. 接收用户研究方案，自主执行全流程（提取→搜索→选择→下载→QC→归一化→批次校正→报告）
2. 验证 Graduated Autonomy 模型在实际使用中的效果，根据反馈微调自主权分级
3. 根据实际使用积累 Core Lessons 到 MEMORY.md
4. 等待 Phase 2 集成：lakeFS 版本控制、LaminDB 本体验证

## Recent Decisions
- [2026-03-20] 引入 Graduated Autonomy（分级自主权）模型，替代原来的逐步确认模式。参考 Anthropic/OpenAI/Google Agent 工程最佳实践
- [2026-03-19] 新增 UniProt + PDB 数据源工具，覆盖蛋白质序列/结构检索
- [2026-03-19] 引入 Muon 多组学处理，支持 CITE-seq/Multiome/Spatial
- [2026-03-19] 实现本地版本管理（snapshot/list/restore），作为 Phase 1 lakeFS 替代
- [2026-03-19] 添加拒绝超范围任务的行为边界
- [2026-03-15] 使用 GEOparse 作为 GEO 数据下载的主要工具（比直接 FTP 更稳定）
- [2026-03-15] 默认 QC 参数：min_genes=200, min_cells=3, mt_pct<20%

## Incoming Messages
<!-- 来自其他 Agent 的 inbox 消息将追加在此处 -->
