# Topic: Scanpy 质控 (QC)

> **关键词**: Scanpy, QC, 质控, 线粒体, 过滤, doublet, Scrublet
> **写入者**: Data Agent
> **最后更新**: 2026-03-19

---

## 核心知识

### 标准 QC 流程

1. 计算 QC 指标: `sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"])`
2. 过滤低质量细胞: `sc.pp.filter_cells(adata, min_genes=200)`
3. 过滤低表达基因: `sc.pp.filter_genes(adata, min_cells=3)`
4. 过滤高线粒体细胞: `adata = adata[adata.obs["pct_counts_mt"] < 20]`

### 线粒体基因前缀

| 物种 | 前缀 | 示例 |
|------|------|------|
| Human | MT- | MT-CO1, MT-ND1 |
| Mouse | mt- | mt-Co1, mt-Nd1 |
| 某些注释 | Mt- | Mt-Co1 |

工具自动检测前缀，无需手动指定。

### QC 参数调整指南

| 场景 | min_genes | mt_pct | 说明 |
|------|-----------|--------|------|
| 默认 | 200 | 20% | 适用于大多数 scRNA-seq |
| 心脏/肌肉组织 | 200 | 40% | 这些组织线粒体含量天然较高 |
| 免疫细胞 PBMC | 200 | 15% | 免疫细胞线粒体含量较低 |
| Spatial 数据 | 100 | 30% | Spatial 每 spot 基因数较少 |

### 停止条件

- QC 后细胞数 < 500: 停止处理，建议用户放宽参数
- QC 后基因数 < 2000: 停止处理，检查数据质量

### Doublet 检测 (Scrublet)

- 适用于 > 5000 细胞的数据集
- 典型 doublet rate: 5-10%
- 如果 doublet rate > 20%，可能是参数问题而非真实 doublet

### 常见陷阱

- **重复 log1p**: 如果数据已经 log 转换，不要再 log1p
- **单位混用**: 确认数据是 raw counts 而非 TPM/FPKM
- **基因名格式**: ENSEMBL ID vs Gene Symbol，影响 MT- 检测
