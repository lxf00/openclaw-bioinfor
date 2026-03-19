# Data Agent 独立工作版设计文档

> **版本**: v1.0 | **创建日期**: 2026-03-19
> **设计原则**: Data Agent 先独立运行，处理结果保存到本地或返回给用户。暂不涉及跨 Agent 通信。
> **与现有文档的关系**: 本文档是 BioOpenClaw v0.1/v0.2/v0.3 设计文档的 **Phase 1 实施方案**，不替代原始设计。

---

## 一、设计依据

| 文档 | 对本方案的贡献 |
|------|-------------|
| v0.1 (BioOpenClaw_Framework_Design.pdf) | Data Agent 核心职责定义：数据全生命周期管理（GEO/TCGA/CellxGene）、Scanpy QC、批次校正、AnnData 标准化 |
| v0.2 (BioOpenClaw_v0.2_优化设计文档_updated.docx) | 四层数据架构设计（lakeFS/LaminDB/TileDB-SOMA/知识图谱），Phase 1 简化为本地文件版本管理 |
| v0.3 (BioOpenClaw_v0.3_持久化记忆系统设计.md) | 三层 Markdown 记忆架构，替代外部数据库 |

### Phase 1 简化映射

| v0.2 设计 | Phase 1 替代 |
|-----------|-------------|
| Layer 1: lakeFS 版本控制 | 本地文件版本管理 (data/versions/) |
| Layer 2: LaminDB 本体验证 | 手动验证 + AnnData 标准化 |
| Layer 3: TileDB-SOMA 存储 | 标准 .h5ad 文件 |
| Layer 4: 知识图谱 | Markdown 实验记录 |

---

## 二、架构概览

```
用户（命令行/飞书/OpenClaw）
    │
    ▼
Data OpenClaw (LLM Core)
    │  系统提示词 + SOUL.md
    │  研究方案解析 / 决策 / 报告
    │
    ▼ MCP 调用
Data Agent MCP Server (Python)
    ├── 数据发现: search_datasets, download_geo_data, download_tcga_data, query_cellxgene
    ├── 数据处理: run_scanpy_qc, run_batch_correction, normalize_data, convert_data_format
    └── 数据管理: inspect_dataset, generate_qc_report, run_pipeline
    │
    ▼ 输出
    ├── data/processed/   → .h5ad 文件
    ├── data/reports/     → QC 报告
    ├── data/lineage/     → 谱系追踪 JSON
    └── shared_memory/experiments/ → 实验记录
```

---

## 三、MCP 工具清单（12 个）

### 数据发现（4 个）

| 工具 | 功能 | 批次 |
|------|------|------|
| search_datasets | 根据研究方案智能搜索 GEO/TCGA/CellxGene | Batch 2 |
| download_geo_data | GEO 数据下载（增强版：checksum + 数据单位检测） | Batch 1 |
| download_tcga_data | TCGA 数据下载（GDC API） | Batch 2 |
| query_cellxgene | CellxGene Census 查询 | Batch 2 |

### 数据处理（4 个）

| 工具 | 功能 | 批次 |
|------|------|------|
| run_scanpy_qc | Scanpy QC（增强版：doublet 检测 + 自动 mt 前缀） | Batch 1 |
| run_batch_correction | 批次校正（Harmony / Combat / scVI） | Batch 2 |
| normalize_data | 数据归一化（含 log 状态检测） | Batch 1 |
| convert_data_format | 格式转换（10x_mtx/csv/loom → h5ad） | Batch 1 |

### 数据管理（4 个）

| 工具 | 功能 | 批次 |
|------|------|------|
| inspect_dataset | 数据检视（shape, 单位, log 状态, 批次） | Batch 1 |
| generate_qc_report | 生成 Markdown QC 报告 | Batch 2 |
| run_pipeline | 管道编排（多步骤自动化） | Batch 3 |

### 内部模块（2 个）

| 模块 | 功能 | 批次 |
|------|------|------|
| validators.py | 数据验证检查点（前置/后置验证） | Batch 1 |
| lineage.py | 谱系追踪（JSON 记录） | Batch 1 |

---

## 四、数据验证检查点

每个工具内嵌前置/后置验证，验证失败返回结构化错误（不抛异常）：

| 工具 | 前置验证 | 后置验证 |
|------|---------|---------|
| download_geo_data | -- | MD5/SHA256 checksum；数据单位和 log 状态检测 |
| run_scanpy_qc | 数据单位确认；log 状态检测 | cell/gene 数量断言；QC 指标分布 |
| normalize_data | log 状态检测（防止重复 log1p） | 归一化后值域检查 |
| run_batch_correction | batch_key 存在性；batch >= 2 | 校正前后 batch 混合度对比 |
| convert_data_format | 输入文件格式检测 | 输出 AnnData 有效性 |

---

## 五、数据谱系追踪

每步操作自动记录到 `data/lineage/<project_name>.json`：

```json
{
  "project": "BRCA1_scRNA",
  "lineage": [
    {
      "step": 1,
      "operation": "download_geo_data",
      "input": null,
      "output": "data/raw/GSE123456/",
      "params": {"gse_id": "GSE123456"},
      "timestamp": "2026-03-19T10:30:00",
      "checksum": "sha256:abc123...",
      "duration_seconds": 120
    }
  ]
}
```

---

## 六、系统提示词核心逻辑

### 方案解析（收到研究方案时）

从方案文本中提取 7 个要素：
1. 研究对象（基因/蛋白/通路）
2. 物种
3. 数据类型（scRNA-seq / bulk RNA-seq / spatial）
4. 疾病/组织
5. 样本要求（最少样本数、配对需求）
6. 时间范围
7. 特殊需求（平台、处理状态）

### 决策规则

- QC: min_genes=200, min_cells=3, mt_pct<20%（心脏/肌肉可放宽到 40%）
- 批次校正: <= 3 batch 用 Harmony，> 3 batch 用 scVI，单 batch 跳过
- 强制检查: 处理前确认 FPKM/TPM/counts；检测到 log 转换则跳过 log1p
- 停止条件: QC 后 cells < 500 或 genes < 2000 时停止并报告

---

## 七、独立工作模式

1. **用户 → Data Agent**: 通过命令行/飞书/OpenClaw 发送研究方案或处理指令
2. **Data Agent → 用户**: 返回搜索结果、处理状态、QC 报告、文件路径
3. **数据输出**: `data/processed/<project>/` (.h5ad)
4. **QC 报告**: `data/reports/<project>_qc_report.md`
5. **实验记录**: `shared_memory/experiments/YYYY-MM-DD_<name>.md`
6. **谱系记录**: `data/lineage/<project>.json`
7. **暂不实现**: inbox 消息、跨 Agent 通信、Watcher 监控

---

## 八、实施批次

- **Batch 1**: 核心工具（QC + 下载 + 检视 + 归一化 + 格式转换 + 验证 + 谱系 + 测试）
- **Batch 2**: 智能搜索 + TCGA + CellxGene + 批次校正 + QC 报告
- **Batch 3**: 管道编排 + 端到端测试 + 文档
