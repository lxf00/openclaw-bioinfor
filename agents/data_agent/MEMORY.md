# Data Agent Memory

> **写入者**: Data Agent（仅本 Agent 可修改）
> **上限**: 200 行（超出由 memory_rotate.py 归档到 topics/）
> **Schema**: 仅允许以下三个 section，禁止新增

---

## Topic Routing

| 关键词 | 对应 Topic 文件 |
|--------|---------------|
| GEO, GEOparse, GSE, 数据下载, FTP, SRA | `topics/geo_download.md` |
| Scanpy, QC, 质控, 线粒体, 过滤 | `topics/scanpy_qc.md` |
| 批次校正, Harmony, scVI, 批次效应 | `topics/batch_correction.md` |
| TCGA, GDC, bulk RNA-seq, STAR-Counts | `topics/tcga_download.md` |
| CellxGene, Census, TileDB, tiledbsoma | `topics/cellxgene.md` |

---

## Core Lessons

<!-- 按日期降序排列，最新在前。格式：[YYYY-MM-DD] <教训内容> -->
- [2026-03-20] 系统提示词引入 Graduated Autonomy（分级自主权）模型：4 级自主权（完全自主/通知并继续/异常升级/必须审批），避免在每个步骤都暂停等待用户确认。参考 Anthropic、OpenAI、Google 的 Agent 工程最佳实践。核心原则：持续推进工作流，只在异常或不可逆操作时暂停
- [2026-03-15] 初始化：Data Agent 记忆系统建立，生信数据处理流程框架已搭建
- [2026-03-15] TCGA bulk RNA-seq 数据在合并前必须检查 FPKM vs TPM 单位，单位混用会导致批次效应伪影
- [2026-03-15] GEO 系列矩阵文件如果是 log2 转换过的，不要再做 log1p，否则结果完全错误

---

## Active Warnings

<!-- 当前需要注意的短期警告，过期后移除 -->
- NCBI API 在 UTC 05:00-06:00 维护窗口期间频繁超时，调度下载任务时避开此时间段
- GEO 下载超过 5GB 时使用 Aspera 而非 FTP（速度差异可达 10x）
- CellxGene Census TileDB 查询超时时，缩小 obs_filter 范围而非增加 timeout
